from typing import Any
from uuid import UUID

from langchain_core.tools import BaseTool, tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools import (
    CleanupWorkspaceFoldersArgs,
    CreateCharacterAssetArgs,
    CreateChapterWithContentArgs,
    CreateRelationshipEdgeArgs,
    CreateTimelineEventArgs,
    CreateWorldRuleArgs,
    CreateWorkspaceNodeArgs,
    DeleteCharacterStateArgs,
    DeleteCreativeAssetArgs,
    DeleteCreativeAssetsArgs,
    DeleteRelationshipEdgeArgs,
    DeleteTimelineEventArgs,
    ListMaterialChangesArgs,
    ListCharacterStatesArgs,
    ListCreativeAssetsArgs,
    ListDocumentVersionsArgs,
    ListMemoryItemsArgs,
    ListMemoryReviewItemsArgs,
    ListTimelineEventsArgs,
    ListWorkspaceNodesArgs,
    OrganizeWorkspaceTreeArgs,
    SaveKeyMemoryArgs,
    ProposeDocumentUpdateArgs,
    ProposeRewriteArgs,
    ProposeSelectionReplaceArgs,
    ProposeVersionRestoreArgs,
    ReadDocumentArgs,
    ReorderTimelineEventsArgs,
    SearchMemoryArgs,
    SearchRagArgs,
    SplitChapterByMaxCharsArgs,
    RestoreWorkspaceNodeArgs,
    TrashWorkspaceNodeArgs,
    WriteDocumentContentArgs,
    UpdateCharacterStateArgs,
    UpdateCreativeAssetArgs,
    UpdateRelationshipEdgeArgs,
    UpdateTimelineEventArgs,
    UpdateNovelArgs,
    UpdateWorkspaceNodeArgs,
    draft_rewrite,
    get_agent_tools,
)
from app.models import (
    CharacterState,
    CreativeAsset,
    Document,
    MemoryItem,
    MemoryReviewItem,
    ModelProfile,
    Novel,
    TimelineEvent,
)
from app.services.document_actions import (
    create_document_update_proposal,
    create_selection_replace_proposal,
    create_version_restore_proposal,
    get_owned_document,
    list_owned_document_versions,
)
from app.services.materials import (
    create_character_state,
    create_creative_asset,
    create_relationship_edge,
    create_timeline_event,
    deduplicate_character_states,
    delete_character_state,
    delete_creative_asset,
    delete_creative_assets,
    delete_relationship_edge,
    delete_timeline_event,
    list_material_changes,
    prepare_timeline_events,
    reorder_timeline_events,
    update_character_state_record,
    update_creative_asset,
    update_relationship_edge,
    update_timeline_event,
)
from app.services.memory import create_memory_item
from app.services.memory_search import search_memory_items
from app.services.rag import extract_text_from_prosemirror, search_rag_chunks
from app.services.workspace_actions import (
    cleanup_workspace_folders,
    create_chapter_with_content,
    create_workspace_node,
    list_workspace_nodes,
    organize_workspace_tree,
    restore_workspace_node,
    split_chapter_by_max_chars,
    trash_workspace_node,
    update_workspace_node,
    write_document_content,
)


def build_runtime_tools(
    session: AsyncSession,
    *,
    model_profile: ModelProfile | None,
    owner_id: UUID | None = None,
    novel_id: UUID | None = None,
) -> list[BaseTool]:
    def scoped_ids() -> tuple[UUID, UUID] | None:
        if owner_id is None or novel_id is None:
            return None
        return owner_id, novel_id

    def current_novel_id(requested_novel_id: str) -> UUID:
        return novel_id if novel_id is not None else UUID(requested_novel_id)

    @tool("search_memory", args_schema=SearchMemoryArgs)
    async def search_memory_runtime(novel_id: str, query: str, limit: int = 8) -> dict[str, Any]:
        """Search approved novel memory items."""
        results = await search_memory_items(session, novel_id=current_novel_id(novel_id), query=query, limit=limit)
        return {"status": "ok", "results": results}

    @tool("search_rag", args_schema=SearchRagArgs)
    async def search_rag_runtime(novel_id: str, query: str, limit: int = 8) -> dict[str, Any]:
        """Search vector-indexed RAG chunks."""
        try:
            chunks = await search_rag_chunks(
                session,
                novel_id=current_novel_id(novel_id),
                query=query,
                limit=limit,
                model_profile=model_profile,
            )
            results = [
                {"text": chunk.text, "source_type": chunk.source_type, "source_id": chunk.source_id}
                for chunk in chunks
            ]
        except Exception:
            results = []
        return {"status": "ok", "results": results}

    @tool("read_document", args_schema=ReadDocumentArgs)
    async def read_document_runtime(document_id: str) -> dict[str, Any]:
        """Read a document by id."""
        scope = scoped_ids()
        if scope is None:
            document = await session.scalar(select(Document).where(Document.id == UUID(document_id)))
        else:
            try:
                document = await get_owned_document(
                    session,
                    owner_id=scope[0],
                    novel_id=scope[1],
                    document_id=UUID(document_id),
                )
            except Exception:
                document = None
        if document is None:
            return {"status": "error", "message": "文档不存在。"}
        return {
            "status": "ok",
            "document_id": document_id,
            "content": extract_text_from_prosemirror(document.content),
        }

    @tool("propose_document_update", args_schema=ProposeDocumentUpdateArgs)
    async def propose_document_update_runtime(document_id: str, content: str) -> dict[str, Any]:
        """Propose a full chapter body replacement; user must confirm before it applies."""
        scope = scoped_ids()
        if scope is None:
            return {"status": "error", "message": "工具缺少当前用户或小说作用域。"}
        try:
            confirmation = await create_document_update_proposal(
                session,
                owner_id=scope[0],
                novel_id=scope[1],
                document_id=UUID(document_id),
                content=content,
            )
        except Exception as exc:
            return {"status": "error", "message": getattr(exc, "detail", str(exc))}
        return {
            "status": "ok",
            "action_type": "confirmation_created",
            "confirmation_id": str(confirmation.id),
            "message": "正文更新方案已生成，请确认后应用。",
        }

    @tool("write_document_content", args_schema=WriteDocumentContentArgs)
    async def write_document_content_runtime(document_id: str, content: str) -> dict[str, Any]:
        """Atomically replace a chapter body and save immediately without confirmation."""
        scope = scoped_ids()
        if scope is None:
            return {"status": "error", "message": "工具缺少当前用户或小说作用域。"}
        try:
            result = await write_document_content(
                session,
                owner_id=scope[0],
                novel_id=scope[1],
                document_id=UUID(document_id),
                content=content,
            )
        except Exception as exc:
            return {"status": "error", "message": getattr(exc, "detail", str(exc))}
        return result

    @tool("propose_selection_replace", args_schema=ProposeSelectionReplaceArgs)
    async def propose_selection_replace_runtime(
        document_id: str, selected_text: str, replacement_text: str
    ) -> dict[str, Any]:
        """Propose replacing one unique text selection after user confirmation."""
        scope = scoped_ids()
        if scope is None:
            return {"status": "error", "message": "工具缺少当前用户或小说作用域。"}
        try:
            confirmation = await create_selection_replace_proposal(
                session,
                owner_id=scope[0],
                novel_id=scope[1],
                document_id=UUID(document_id),
                selected_text=selected_text,
                replacement_text=replacement_text,
            )
        except Exception as exc:
            return {"status": "error", "message": getattr(exc, "detail", str(exc))}
        return {
            "status": "ok",
            "action_type": "confirmation_created",
            "confirmation_id": str(confirmation.id),
            "message": "选区替换方案已生成，请确认后应用。",
        }

    @tool("list_document_versions", args_schema=ListDocumentVersionsArgs)
    async def list_document_versions_runtime(document_id: str) -> dict[str, Any]:
        """List saved versions for a document in the current novel."""
        scope = scoped_ids()
        if scope is None:
            return {"status": "error", "message": "工具缺少当前用户或小说作用域。"}
        try:
            versions = await list_owned_document_versions(
                session,
                owner_id=scope[0],
                novel_id=scope[1],
                document_id=UUID(document_id),
            )
        except Exception as exc:
            return {"status": "error", "message": getattr(exc, "detail", str(exc))}
        return {
            "status": "ok",
            "versions": [
                {
                    "id": str(version.id),
                    "source": version.source,
                    "content": extract_text_from_prosemirror(version.content),
                    "created_at": version.created_at.isoformat(),
                }
                for version in versions
            ],
        }

    @tool("propose_version_restore", args_schema=ProposeVersionRestoreArgs)
    async def propose_version_restore_runtime(document_id: str, version_id: str) -> dict[str, Any]:
        """Propose restoring a saved document version after user confirmation."""
        scope = scoped_ids()
        if scope is None:
            return {"status": "error", "message": "工具缺少当前用户或小说作用域。"}
        try:
            confirmation = await create_version_restore_proposal(
                session,
                owner_id=scope[0],
                novel_id=scope[1],
                document_id=UUID(document_id),
                version_id=UUID(version_id),
            )
        except Exception as exc:
            return {"status": "error", "message": getattr(exc, "detail", str(exc))}
        return {
            "status": "ok",
            "action_type": "confirmation_created",
            "confirmation_id": str(confirmation.id),
            "message": "版本恢复方案已生成，请确认后应用。",
        }

    @tool("restore_workspace_node", args_schema=RestoreWorkspaceNodeArgs)
    async def restore_workspace_node_runtime(node_id: str) -> dict[str, Any]:
        """Restore a trashed workspace node in the current novel."""
        scope = scoped_ids()
        if scope is None:
            return {"status": "error", "message": "工具缺少当前用户或小说作用域。"}
        return await restore_workspace_node(session, novel_id=scope[1], node_id=UUID(node_id))

    @tool("update_novel", args_schema=UpdateNovelArgs)
    async def update_novel_runtime(
        novel_id: str,
        title: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Rename a novel or update its description."""
        if title is None and description is None:
            return {"status": "error", "message": "请提供要更新的标题或简介。"}
        resolved_novel_id = current_novel_id(novel_id)
        novel = await session.scalar(select(Novel).where(Novel.id == resolved_novel_id))
        if novel is None:
            return {"status": "error", "message": "小说不存在。"}
        if title is not None:
            novel.title = title
        if description is not None:
            novel.description = description
        await session.commit()
        await session.refresh(novel)
        message = f"已将小说重命名为「{novel.title}」。" if title is not None else "已更新小说信息。"
        return {
            "status": "ok",
            "message": message,
            "novel_updated": {
                "id": str(novel.id),
                "title": novel.title,
                "description": novel.description,
            },
        }

    @tool("list_workspace_nodes", args_schema=ListWorkspaceNodesArgs)
    async def list_workspace_nodes_runtime(novel_id: str) -> dict[str, Any]:
        """List nodes with document ids and content state; use existing document_id for old or empty chapters."""
        nodes = await list_workspace_nodes(session, novel_id=current_novel_id(novel_id))
        return {"status": "ok", "nodes": nodes}

    @tool("create_workspace_node", args_schema=CreateWorkspaceNodeArgs)
    async def create_workspace_node_runtime(
        novel_id: str, title: str, node_type: str, parent_id: str | None = None
    ) -> dict[str, Any]:
        """Create a folder, chapter, note, or draft node shell."""
        return await create_workspace_node(
            session,
            novel_id=current_novel_id(novel_id),
            title=title,
            node_type=node_type,
            parent_id=UUID(parent_id) if parent_id else None,
        )

    @tool("create_chapter_with_content", args_schema=CreateChapterWithContentArgs)
    async def create_chapter_with_content_runtime(
        novel_id: str,
        title: str,
        content: str,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new chapter only when no matching chapter exists; never duplicate an existing chapter title."""
        return await create_chapter_with_content(
            session,
            novel_id=current_novel_id(novel_id),
            title=title,
            content=content,
            parent_id=UUID(parent_id) if parent_id else None,
        )

    @tool("update_workspace_node", args_schema=UpdateWorkspaceNodeArgs)
    async def update_workspace_node_runtime(
        novel_id: str,
        node_id: str,
        title: str | None = None,
        parent_id: str | None = None,
        position: int | None = None,
    ) -> dict[str, Any]:
        """Atomically rename, move, or reorder a chapter/folder node."""
        return await update_workspace_node(
            session,
            novel_id=current_novel_id(novel_id),
            node_id=UUID(node_id),
            title=title,
            parent_id=UUID(parent_id) if parent_id else None,
            position=position,
        )

    @tool("trash_workspace_node", args_schema=TrashWorkspaceNodeArgs)
    async def trash_workspace_node_runtime(novel_id: str, node_id: str) -> dict[str, Any]:
        """Move a workspace node to trash."""
        return await trash_workspace_node(
            session, novel_id=current_novel_id(novel_id), node_id=UUID(node_id)
        )

    @tool("split_chapter_by_max_chars", args_schema=SplitChapterByMaxCharsArgs)
    async def split_chapter_by_max_chars_runtime(
        novel_id: str, node_id: str, max_chars: int = 3000
    ) -> dict[str, Any]:
        """Split an overlong chapter into multiple parts, each at most max_chars."""
        scope = scoped_ids()
        if scope is None:
            return {"status": "error", "message": "工具缺少当前用户或小说作用域。"}
        return await split_chapter_by_max_chars(
            session,
            novel_id=current_novel_id(novel_id),
            owner_id=scope[0],
            node_id=UUID(node_id),
            max_chars=max_chars,
        )

    @tool("organize_workspace_tree", args_schema=OrganizeWorkspaceTreeArgs)
    async def organize_workspace_tree_runtime(novel_id: str, instruction: str = "") -> dict[str, Any]:
        """Organize draft-like chapters into the drafts folder."""
        return await organize_workspace_tree(session, novel_id=current_novel_id(novel_id))

    @tool("cleanup_workspace_folders", args_schema=CleanupWorkspaceFoldersArgs)
    async def cleanup_workspace_folders_runtime(novel_id: str, instruction: str = "") -> dict[str, Any]:
        """Delete folders and move chapters to root when possible."""
        return await cleanup_workspace_folders(
            session, novel_id=current_novel_id(novel_id), message=instruction
        )

    @tool("list_memory_items", args_schema=ListMemoryItemsArgs)
    async def list_memory_items_runtime(novel_id: str) -> dict[str, Any]:
        """List approved memory items."""
        items = list(
            await session.scalars(
                select(MemoryItem)
                .where(MemoryItem.novel_id == current_novel_id(novel_id))
                .order_by(MemoryItem.created_at)
            )
        )
        return {
            "status": "ok",
            "items": [
                {
                    "id": str(item.id),
                    "memory_type": item.memory_type,
                    "title": item.title,
                    "body": item.body,
                    "importance": item.importance,
                }
                for item in items
            ],
        }

    @tool("list_memory_review_items", args_schema=ListMemoryReviewItemsArgs)
    async def list_memory_review_items_runtime(novel_id: str) -> dict[str, Any]:
        """List memory review queue items."""
        items = list(
            await session.scalars(
                select(MemoryReviewItem)
                .where(MemoryReviewItem.novel_id == current_novel_id(novel_id))
                .order_by(MemoryReviewItem.created_at)
            )
        )
        return {
            "status": "ok",
            "items": [
                {
                    "id": str(item.id),
                    "memory_type": item.memory_type,
                    "title": item.title,
                    "body": item.body,
                    "importance": item.importance,
                    "status": item.status,
                }
                for item in items
            ],
        }

    @tool("save_key_memory", args_schema=SaveKeyMemoryArgs)
    async def save_key_memory_runtime(
        novel_id: str, title: str, body: str, importance: int = 80
    ) -> dict[str, Any]:
        """Save durable novel memory without approval."""
        scope = scoped_ids()
        if scope is None:
            return {
                "status": "error",
                "action_type": "memory_save_failed",
                "message": "Authenticated owner and novel scope are required to save memory.",
            }
        memory = await create_memory_item(
            session,
            novel_id=current_novel_id(novel_id),
            memory_type="key_memory",
            title=title,
            body=body,
            importance=importance,
            metadata={"source": "agent_inferred"},
        )
        await session.commit()
        await session.refresh(memory)
        return {
            "status": "ok",
            "action_type": "memory_saved",
            "message": f"已保存关键记忆「{title}」。",
            "memory_item_id": str(memory.id),
        }

    @tool("list_creative_assets", args_schema=ListCreativeAssetsArgs)
    async def list_creative_assets_runtime(novel_id: str) -> dict[str, Any]:
        """List creative assets such as characters and world entries."""
        assets = list(
            await session.scalars(
                select(CreativeAsset).where(CreativeAsset.novel_id == current_novel_id(novel_id))
            )
        )
        return {
            "status": "ok",
            "assets": [
                {"id": str(asset.id), "asset_type": asset.asset_type, "name": asset.name, "summary": asset.summary}
                for asset in assets
            ],
        }

    @tool("create_character_asset", args_schema=CreateCharacterAssetArgs)
    async def create_character_asset_runtime(novel_id: str, name: str, summary: str) -> dict[str, Any]:
        """Create a character creative asset."""
        asset = await create_creative_asset(
            session,
            novel_id=current_novel_id(novel_id),
            asset_type="character",
            name=name,
            summary=summary,
            actor_source="agent",
        )
        await session.commit()
        return {
            "status": "ok",
            "action_type": "create_character_asset",
            "message": f"已创建角色「{name}」。",
            "id": str(asset.id),
        }

    @tool("create_world_rule", args_schema=CreateWorldRuleArgs)
    async def create_world_rule_runtime(novel_id: str, title: str, rule: str) -> dict[str, Any]:
        """Create a worldbuilding rule asset."""
        asset = await create_creative_asset(
            session,
            novel_id=current_novel_id(novel_id),
            asset_type="world_rule",
            name=title,
            summary=rule,
            actor_source="agent",
        )
        await session.commit()
        return {
            "status": "ok",
            "action_type": "create_world_rule",
            "message": f"已创建世界规则「{title}」。",
            "id": str(asset.id),
        }

    @tool("update_creative_asset", args_schema=UpdateCreativeAssetArgs)
    async def update_creative_asset_runtime(
        novel_id: str,
        asset_id: str,
        asset_type: str | None = None,
        name: str | None = None,
        summary: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing creative asset by id."""
        asset = await update_creative_asset(
            session,
            novel_id=current_novel_id(novel_id),
            asset_id=UUID(asset_id),
            asset_type=asset_type,
            name=name,
            summary=summary,
            actor_source="agent",
        )
        if asset is None:
            return {"status": "error", "message": "创作资产不存在。"}
        await session.commit()
        return {
            "status": "ok",
            "action_type": "update_creative_asset",
            "message": f"已更新创作资产「{asset.name}」。",
            "id": str(asset.id),
        }

    @tool("delete_creative_asset", args_schema=DeleteCreativeAssetArgs)
    async def delete_creative_asset_runtime(novel_id: str, asset_id: str) -> dict[str, Any]:
        """Delete one creative asset by id. Execute directly; never ask the user to delete manually."""
        deleted = await delete_creative_asset(
            session,
            novel_id=current_novel_id(novel_id),
            asset_id=UUID(asset_id),
            actor_source="agent",
        )
        if not deleted:
            return {"status": "error", "message": "创作资产不存在。"}
        await session.commit()
        return {
            "status": "ok",
            "action_type": "delete_creative_asset",
            "message": "已删除创作资产。",
            "id": asset_id,
        }

    @tool("delete_creative_assets", args_schema=DeleteCreativeAssetsArgs)
    async def delete_creative_assets_runtime(novel_id: str, asset_ids: list[str]) -> dict[str, Any]:
        """Delete multiple creative assets by id in one batch."""
        result = await delete_creative_assets(
            session,
            novel_id=current_novel_id(novel_id),
            asset_ids=[UUID(asset_id) for asset_id in asset_ids],
            actor_source="agent",
        )
        if not result["deleted"]:
            return {"status": "error", "message": "未找到可删除的创作资产。"}
        await session.commit()
        missing_count = len(result["missing"])
        message = f"已删除 {len(result['deleted'])} 个创作资产。"
        if missing_count:
            message += f" {missing_count} 个 id 未找到。"
        return {
            "status": "ok",
            "action_type": "delete_creative_assets",
            "message": message,
            "deleted_ids": result["deleted"],
            "missing_ids": result["missing"],
        }

    @tool("list_timeline_events", args_schema=ListTimelineEventsArgs)
    async def list_timeline_events_runtime(novel_id: str) -> dict[str, Any]:
        """List timeline events."""
        events = list(
            await session.scalars(
                select(TimelineEvent).where(TimelineEvent.novel_id == current_novel_id(novel_id))
            )
        )
        prepared_events = prepare_timeline_events(events)
        return {
            "status": "ok",
            "events": [
                {
                    "id": str(event.id),
                    "title": event.title,
                    "event_time": event.event_time,
                    "summary": event.summary,
                    "position": event.position,
                }
                for event in prepared_events
            ],
        }

    @tool("create_timeline_event", args_schema=CreateTimelineEventArgs)
    async def create_timeline_event_runtime(
        novel_id: str, title: str, event_time: str, summary: str
    ) -> dict[str, Any]:
        """Create a timeline event."""
        event = await create_timeline_event(
            session,
            novel_id=current_novel_id(novel_id),
            title=title,
            event_time=event_time,
            summary=summary,
            actor_source="agent",
        )
        await session.commit()
        return {
            "status": "ok",
            "action_type": "create_timeline_event",
            "message": f"已创建时间线事件「{title}」。",
            "id": str(event.id),
        }

    @tool("update_timeline_event", args_schema=UpdateTimelineEventArgs)
    async def update_timeline_event_runtime(
        novel_id: str,
        event_id: str,
        title: str | None = None,
        event_time: str | None = None,
        summary: str | None = None,
        position: int | None = None,
    ) -> dict[str, Any]:
        """Update an existing timeline event by id."""
        event = await update_timeline_event(
            session,
            novel_id=current_novel_id(novel_id),
            event_id=UUID(event_id),
            title=title,
            event_time=event_time,
            summary=summary,
            position=position,
            actor_source="agent",
        )
        if event is None:
            return {"status": "error", "message": "时间线事件不存在。"}
        await session.commit()
        return {
            "status": "ok",
            "action_type": "update_timeline_event",
            "message": f"已更新时间线事件「{event.title}」。",
            "id": str(event.id),
            "position": event.position,
        }

    @tool("reorder_timeline_events", args_schema=ReorderTimelineEventsArgs)
    async def reorder_timeline_events_runtime(novel_id: str, event_ids: list[str]) -> dict[str, Any]:
        """Reorder timeline events by providing event ids in the desired display order."""
        events = await reorder_timeline_events(
            session,
            novel_id=current_novel_id(novel_id),
            event_ids=[UUID(event_id) for event_id in event_ids],
            actor_source="agent",
        )
        if events is None:
            return {"status": "error", "message": "时间线事件不存在。"}
        await session.commit()
        prepared_events = prepare_timeline_events(events)
        return {
            "status": "ok",
            "action_type": "reorder_timeline_events",
            "message": f"已调整 {len(prepared_events)} 个时间线事件的显示顺序。",
            "events": [
                {
                    "id": str(event.id),
                    "title": event.title,
                    "event_time": event.event_time,
                    "position": event.position,
                }
                for event in prepared_events
            ],
        }

    @tool("delete_timeline_event", args_schema=DeleteTimelineEventArgs)
    async def delete_timeline_event_runtime(novel_id: str, event_id: str) -> dict[str, Any]:
        """Delete a timeline event by id."""
        deleted = await delete_timeline_event(
            session,
            novel_id=current_novel_id(novel_id),
            event_id=UUID(event_id),
            actor_source="agent",
        )
        if not deleted:
            return {"status": "error", "message": "时间线事件不存在。"}
        await session.commit()
        return {
            "status": "ok",
            "action_type": "delete_timeline_event",
            "message": "已删除时间线事件。",
            "id": event_id,
        }

    @tool("list_character_states", args_schema=ListCharacterStatesArgs)
    async def list_character_states_runtime(novel_id: str) -> dict[str, Any]:
        """List character states."""
        states = list(
            await session.scalars(
                select(CharacterState).where(CharacterState.novel_id == current_novel_id(novel_id))
            )
        )
        deduplicated_states = deduplicate_character_states(states)
        return {
            "status": "ok",
            "states": [
                {
                    "id": str(state.id),
                    "character_name": state.character_name,
                    "state": state.state,
                    "scope": state.scope,
                }
                for state in deduplicated_states
            ],
        }

    @tool("update_character_state", args_schema=UpdateCharacterStateArgs)
    async def update_character_state_runtime(
        novel_id: str,
        character_name: str,
        state: str,
        state_id: str | None = None,
        scope: str | None = None,
    ) -> dict[str, Any]:
        """Create or update a character state snapshot."""
        resolved_novel_id = current_novel_id(novel_id)
        if state_id:
            character_state = await update_character_state_record(
                session,
                novel_id=resolved_novel_id,
                state_id=UUID(state_id),
                character_name=character_name,
                state=state,
                scope=scope,
                actor_source="agent",
            )
            if character_state is None:
                return {"status": "error", "message": "角色状态不存在。"}
            action_type = "update_character_state"
            message = f"已更新角色「{character_state.character_name}」状态。"
        else:
            character_state = await create_character_state(
                session,
                novel_id=resolved_novel_id,
                character_name=character_name,
                state=state,
                scope=scope or "current",
                actor_source="agent",
            )
            action_type = "create_character_state"
            message = f"已记录角色「{character_name}」状态。"
        await session.commit()
        return {
            "status": "ok",
            "action_type": action_type,
            "message": message,
            "id": str(character_state.id),
        }

    @tool("delete_character_state", args_schema=DeleteCharacterStateArgs)
    async def delete_character_state_runtime(novel_id: str, state_id: str) -> dict[str, Any]:
        """Delete a character state record."""
        deleted = await delete_character_state(
            session,
            novel_id=current_novel_id(novel_id),
            state_id=UUID(state_id),
            actor_source="agent",
        )
        if not deleted:
            return {"status": "error", "message": "角色状态不存在。"}
        await session.commit()
        return {
            "status": "ok",
            "action_type": "delete_character_state",
            "message": "已删除角色状态记录。",
            "id": state_id,
        }

    @tool("create_relationship_edge", args_schema=CreateRelationshipEdgeArgs)
    async def create_relationship_edge_runtime(
        novel_id: str,
        source_character: str,
        target_character: str,
        relationship_type: str,
        description: str = "",
    ) -> dict[str, Any]:
        """Create a relationship edge between characters."""
        edge = await create_relationship_edge(
            session,
            novel_id=current_novel_id(novel_id),
            source_character=source_character,
            target_character=target_character,
            relationship_type=relationship_type,
            description=description,
            actor_source="agent",
        )
        await session.commit()
        return {
            "status": "ok",
            "action_type": "create_relationship_edge",
            "message": f"已记录 {source_character} 与 {target_character} 的关系。",
            "id": str(edge.id),
        }

    @tool("update_relationship_edge", args_schema=UpdateRelationshipEdgeArgs)
    async def update_relationship_edge_runtime(
        novel_id: str,
        edge_id: str,
        source_character: str | None = None,
        target_character: str | None = None,
        relationship_type: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing relationship edge by id."""
        edge = await update_relationship_edge(
            session,
            novel_id=current_novel_id(novel_id),
            edge_id=UUID(edge_id),
            source_character=source_character,
            target_character=target_character,
            relationship_type=relationship_type,
            description=description,
            actor_source="agent",
        )
        if edge is None:
            return {"status": "error", "message": "人物关系不存在。"}
        await session.commit()
        return {
            "status": "ok",
            "action_type": "update_relationship_edge",
            "message": f"已更新 {edge.source_character} 与 {edge.target_character} 的关系。",
            "id": str(edge.id),
        }

    @tool("delete_relationship_edge", args_schema=DeleteRelationshipEdgeArgs)
    async def delete_relationship_edge_runtime(novel_id: str, edge_id: str) -> dict[str, Any]:
        """Delete a relationship edge by id."""
        deleted = await delete_relationship_edge(
            session,
            novel_id=current_novel_id(novel_id),
            edge_id=UUID(edge_id),
            actor_source="agent",
        )
        if not deleted:
            return {"status": "error", "message": "人物关系不存在。"}
        await session.commit()
        return {
            "status": "ok",
            "action_type": "delete_relationship_edge",
            "message": "已删除人物关系。",
            "id": edge_id,
        }

    @tool("list_material_changes", args_schema=ListMaterialChangesArgs)
    async def list_material_changes_runtime(
        novel_id: str,
        material_type: str | None = None,
        material_id: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """List recent material create/update/delete history."""
        changes = await list_material_changes(
            session,
            novel_id=current_novel_id(novel_id),
            material_type=material_type,
            material_id=UUID(material_id) if material_id else None,
            limit=limit,
        )
        return {
            "status": "ok",
            "changes": [
                {
                    "id": str(change.id),
                    "material_type": change.material_type,
                    "material_id": str(change.material_id),
                    "action": change.action,
                    "actor_source": change.actor_source,
                    "summary": change.summary,
                    "before_data": change.before_data,
                    "after_data": change.after_data,
                    "created_at": change.created_at.isoformat(),
                }
                for change in changes
            ],
        }

    @tool("propose_rewrite", args_schema=ProposeRewriteArgs)
    async def propose_rewrite_runtime(document_id: str, selected_text: str, instruction: str) -> dict[str, Any]:
        """Draft a rewrite proposal without mutating the document."""
        scope = scoped_ids()
        if scope is not None:
            confirmation = await create_selection_replace_proposal(
                session,
                owner_id=scope[0],
                novel_id=scope[1],
                document_id=UUID(document_id),
                selected_text=selected_text,
                replacement_text=draft_rewrite(selected_text, instruction),
                action_type="rewrite_selection",
            )
            return {
                "status": "ok",
                "action_type": "confirmation_created",
                "confirmation_id": str(confirmation.id),
                "message": "我已草拟改写方案，请确认后再应用。",
            }
        return {
            "action_type": "rewrite_selection",
            "message": "我已草拟改写方案，请确认后再应用。",
            "payload": {
                "document_id": document_id,
                "selected_text": selected_text,
                "replacement_text": draft_rewrite(selected_text, instruction),
            },
        }

    runtime_by_name = {
        "search_memory": search_memory_runtime,
        "search_rag": search_rag_runtime,
        "read_document": read_document_runtime,
        "update_novel": update_novel_runtime,
        "list_workspace_nodes": list_workspace_nodes_runtime,
        "create_workspace_node": create_workspace_node_runtime,
        "create_chapter_with_content": create_chapter_with_content_runtime,
        "write_document_content": write_document_content_runtime,
        "split_chapter_by_max_chars": split_chapter_by_max_chars_runtime,
        "propose_document_update": propose_document_update_runtime,
        "propose_selection_replace": propose_selection_replace_runtime,
        "list_document_versions": list_document_versions_runtime,
        "propose_version_restore": propose_version_restore_runtime,
        "restore_workspace_node": restore_workspace_node_runtime,
        "update_workspace_node": update_workspace_node_runtime,
        "trash_workspace_node": trash_workspace_node_runtime,
        "organize_workspace_tree": organize_workspace_tree_runtime,
        "cleanup_workspace_folders": cleanup_workspace_folders_runtime,
        "list_memory_items": list_memory_items_runtime,
        "list_memory_review_items": list_memory_review_items_runtime,
        "save_key_memory": save_key_memory_runtime,
        "list_creative_assets": list_creative_assets_runtime,
        "create_character_asset": create_character_asset_runtime,
        "create_world_rule": create_world_rule_runtime,
        "update_creative_asset": update_creative_asset_runtime,
        "delete_creative_asset": delete_creative_asset_runtime,
        "delete_creative_assets": delete_creative_assets_runtime,
        "list_timeline_events": list_timeline_events_runtime,
        "create_timeline_event": create_timeline_event_runtime,
        "update_timeline_event": update_timeline_event_runtime,
        "reorder_timeline_events": reorder_timeline_events_runtime,
        "delete_timeline_event": delete_timeline_event_runtime,
        "list_character_states": list_character_states_runtime,
        "update_character_state": update_character_state_runtime,
        "delete_character_state": delete_character_state_runtime,
        "create_relationship_edge": create_relationship_edge_runtime,
        "update_relationship_edge": update_relationship_edge_runtime,
        "delete_relationship_edge": delete_relationship_edge_runtime,
        "list_material_changes": list_material_changes_runtime,
        "propose_rewrite": propose_rewrite_runtime,
    }

    tools: list[BaseTool] = []
    for tool_obj in get_agent_tools():
        tools.append(runtime_by_name.get(tool_obj.name, tool_obj))
    return tools
