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
    ListCharacterStatesArgs,
    ListCreativeAssetsArgs,
    ListDocumentVersionsArgs,
    ListMemoryItemsArgs,
    ListMemoryReviewItemsArgs,
    ListTimelineEventsArgs,
    ListWorkspaceNodesArgs,
    OrganizeWorkspaceTreeArgs,
    ProposeKeyMemoryArgs,
    ProposeDocumentUpdateArgs,
    ProposeRewriteArgs,
    ProposeSelectionReplaceArgs,
    ProposeVersionRestoreArgs,
    ReadDocumentArgs,
    SearchMemoryArgs,
    SearchRagArgs,
    RestoreWorkspaceNodeArgs,
    TrashWorkspaceNodeArgs,
    UpdateCharacterStateArgs,
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
    RelationshipEdge,
    TimelineEvent,
)
from app.services.document_actions import (
    create_document_update_proposal,
    create_selection_replace_proposal,
    create_version_restore_proposal,
    get_owned_document,
    list_owned_document_versions,
)
from app.services.memory_search import search_memory_items
from app.services.rag import extract_text_from_prosemirror, index_text, search_rag_chunks
from app.services.workspace_actions import (
    cleanup_workspace_folders,
    create_chapter_with_content,
    create_workspace_node,
    list_workspace_nodes,
    organize_workspace_tree,
    restore_workspace_node,
    trash_workspace_node,
    update_workspace_node,
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
        """Propose replacing a complete document after user confirmation."""
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

    @tool("list_workspace_nodes", args_schema=ListWorkspaceNodesArgs)
    async def list_workspace_nodes_runtime(novel_id: str) -> dict[str, Any]:
        """List chapter tree nodes including folders, chapters, and trash status."""
        nodes = await list_workspace_nodes(session, novel_id=current_novel_id(novel_id))
        return {"status": "ok", "nodes": nodes}

    @tool("create_workspace_node", args_schema=CreateWorkspaceNodeArgs)
    async def create_workspace_node_runtime(
        novel_id: str, title: str, node_type: str, parent_id: str | None = None
    ) -> dict[str, Any]:
        """Create a folder, chapter, note, or draft node."""
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
        """Create a chapter and persist its complete body in the workspace."""
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
        """Rename or move a workspace node."""
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

    @tool("propose_key_memory", args_schema=ProposeKeyMemoryArgs)
    async def propose_key_memory_runtime(
        novel_id: str, title: str, body: str, importance: int = 80
    ) -> dict[str, Any]:
        """Create a key memory review item for user approval."""
        item = MemoryReviewItem(
            novel_id=current_novel_id(novel_id),
            memory_type="key_memory",
            title=title,
            body=body,
            importance=importance,
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return {
            "status": "ok",
            "action_type": "memory_review",
            "message": f"已提交关键记忆「{title}」，请在记忆页审核。",
            "review_item_id": str(item.id),
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
        asset = CreativeAsset(
            novel_id=current_novel_id(novel_id), asset_type="character", name=name, summary=summary
        )
        session.add(asset)
        await session.flush()
        await index_text(
            session,
            novel_id=current_novel_id(novel_id),
            source_type="creative_asset",
            source_id=str(asset.id),
            text=f"character: {name}\n{summary}",
            metadata={"asset_type": "character"},
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
        asset = CreativeAsset(
            novel_id=current_novel_id(novel_id), asset_type="world_rule", name=title, summary=rule
        )
        session.add(asset)
        await session.flush()
        await index_text(
            session,
            novel_id=current_novel_id(novel_id),
            source_type="creative_asset",
            source_id=str(asset.id),
            text=f"world_rule: {title}\n{rule}",
            metadata={"asset_type": "world_rule"},
        )
        await session.commit()
        return {
            "status": "ok",
            "action_type": "create_world_rule",
            "message": f"已创建世界规则「{title}」。",
            "id": str(asset.id),
        }

    @tool("list_timeline_events", args_schema=ListTimelineEventsArgs)
    async def list_timeline_events_runtime(novel_id: str) -> dict[str, Any]:
        """List timeline events."""
        events = list(
            await session.scalars(
                select(TimelineEvent).where(TimelineEvent.novel_id == current_novel_id(novel_id))
            )
        )
        return {
            "status": "ok",
            "events": [
                {"id": str(event.id), "title": event.title, "event_time": event.event_time, "summary": event.summary}
                for event in events
            ],
        }

    @tool("create_timeline_event", args_schema=CreateTimelineEventArgs)
    async def create_timeline_event_runtime(
        novel_id: str, title: str, event_time: str, summary: str
    ) -> dict[str, Any]:
        """Create a timeline event."""
        event = TimelineEvent(
            novel_id=current_novel_id(novel_id), title=title, event_time=event_time, summary=summary
        )
        session.add(event)
        await session.flush()
        await index_text(
            session,
            novel_id=current_novel_id(novel_id),
            source_type="timeline_event",
            source_id=str(event.id),
            text=f"{event_time}: {title}\n{summary}",
        )
        await session.commit()
        return {
            "status": "ok",
            "action_type": "create_timeline_event",
            "message": f"已创建时间线事件「{title}」。",
            "id": str(event.id),
        }

    @tool("list_character_states", args_schema=ListCharacterStatesArgs)
    async def list_character_states_runtime(novel_id: str) -> dict[str, Any]:
        """List character states."""
        states = list(
            await session.scalars(
                select(CharacterState).where(CharacterState.novel_id == current_novel_id(novel_id))
            )
        )
        return {
            "status": "ok",
            "states": [
                {
                    "id": str(state.id),
                    "character_name": state.character_name,
                    "state": state.state,
                    "scope": state.scope,
                }
                for state in states
            ],
        }

    @tool("update_character_state", args_schema=UpdateCharacterStateArgs)
    async def update_character_state_runtime(novel_id: str, character_name: str, state: str) -> dict[str, Any]:
        """Record a character state snapshot."""
        character_state = CharacterState(
            novel_id=current_novel_id(novel_id), character_name=character_name, state=state, scope="current"
        )
        session.add(character_state)
        await session.flush()
        await index_text(
            session,
            novel_id=current_novel_id(novel_id),
            source_type="character_state",
            source_id=str(character_state.id),
            text=f"{character_name}: {state}",
        )
        await session.commit()
        return {
            "status": "ok",
            "action_type": "update_character_state",
            "message": f"已更新角色「{character_name}」状态。",
            "id": str(character_state.id),
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
        edge = RelationshipEdge(
            novel_id=current_novel_id(novel_id),
            source_character=source_character,
            target_character=target_character,
            relationship_type=relationship_type,
            description=description,
        )
        session.add(edge)
        await session.flush()
        await index_text(
            session,
            novel_id=current_novel_id(novel_id),
            source_type="relationship_edge",
            source_id=str(edge.id),
            text=f"{source_character} {relationship_type} {target_character}: {description}",
        )
        await session.commit()
        return {
            "status": "ok",
            "action_type": "create_relationship_edge",
            "message": f"已记录 {source_character} 与 {target_character} 的关系。",
            "id": str(edge.id),
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
        "list_workspace_nodes": list_workspace_nodes_runtime,
        "create_workspace_node": create_workspace_node_runtime,
        "create_chapter_with_content": create_chapter_with_content_runtime,
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
        "propose_key_memory": propose_key_memory_runtime,
        "list_creative_assets": list_creative_assets_runtime,
        "create_character_asset": create_character_asset_runtime,
        "create_world_rule": create_world_rule_runtime,
        "list_timeline_events": list_timeline_events_runtime,
        "create_timeline_event": create_timeline_event_runtime,
        "list_character_states": list_character_states_runtime,
        "update_character_state": update_character_state_runtime,
        "create_relationship_edge": create_relationship_edge_runtime,
        "propose_rewrite": propose_rewrite_runtime,
    }

    tools: list[BaseTool] = []
    for tool_obj in get_agent_tools():
        tools.append(runtime_by_name.get(tool_obj.name, tool_obj))
    return tools
