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
    DeleteCharacterAttributeArgs,
    DeleteCharacterStateArgs,
    DeleteCreativeAssetArgs,
    DeleteCreativeAssetsArgs,
    DeleteInventoryItemArgs,
    DeleteMapLocationArgs,
    DeleteRelationshipEdgeArgs,
    DeleteMemoryItemArgs,
    DeleteTimelineEventArgs,
    GlobalReplaceKeywordArgs,
    ListCharacterAttributesArgs,
    ListInventoryItemsArgs,
    ListMapLocationsArgs,
    ListMaterialChangesArgs,
    ListCharacterStatesArgs,
    ListCreativeAssetsArgs,
    ListDocumentVersionsArgs,
    ListMemoryItemsArgs,
    ListMemoryReviewItemsArgs,
    ListTimelineEventsArgs,
    ListWorkspaceNodesArgs,
    OrganizeWorkspaceTreeArgs,
    ProposeDocumentUpdateArgs,
    ProposeRewriteArgs,
    ProposeSelectionReplaceArgs,
    ProposeVersionRestoreArgs,
    ReadDocumentArgs,
    ReorderTimelineEventsArgs,
    SaveKeyMemoryArgs,
    ScoreChaptersWithRubricArgs,
    SearchDocumentsByKeywordArgs,
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
    UpsertCharacterAttributeArgs,
    UpsertInventoryItemArgs,
    UpsertMapLocationArgs,
    draft_rewrite,
    get_agent_tools,
)
from app.models import (
    CharacterAttribute,
    CharacterState,
    CreativeAsset,
    Document,
    InventoryItem,
    MapLocation,
    MemoryItem,
    MemoryReviewItem,
    ModelProfile,
    Novel,
    WorkspaceNode,
    TimelineEvent,
)
from app.services.document_actions import (
    create_document_update_proposal,
    create_selection_replace_proposal,
    create_version_restore_proposal,
    get_owned_document,
    list_owned_document_versions,
)
from app.services.document_search import search_novel_documents
from app.services.global_replace import global_replace_keyword
from app.services.materials import (
    create_character_state,
    create_creative_asset,
    create_relationship_edge,
    create_timeline_event,
    deduplicate_character_states,
    delete_character_attribute,
    delete_character_state,
    delete_creative_asset,
    delete_creative_assets,
    delete_inventory_item,
    delete_map_location,
    delete_relationship_edge,
    delete_timeline_event,
    list_character_attributes,
    list_inventory_items,
    list_map_locations,
    list_material_changes,
    prepare_timeline_events,
    reorder_timeline_events,
    update_character_state_record,
    update_creative_asset,
    update_relationship_edge,
    update_timeline_event,
    upsert_character_attribute,
    upsert_inventory_item,
    upsert_map_location,
)
from app.services.memory import create_memory_item, delete_memory_item as delete_memory_item_service
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


def relationship_timeline_metadata(
    *,
    timeline_event_id: str | None,
    timeline_event_time: str | None,
    timeline_title: str | None,
) -> dict[str, str]:
    metadata: dict[str, str] = {}
    if timeline_event_id:
        metadata["timeline_event_id"] = timeline_event_id
    if timeline_event_time:
        metadata["timeline_event_time"] = timeline_event_time
    if timeline_title:
        metadata["timeline_title"] = timeline_title
    return metadata


def character_attribute_payload(attribute: CharacterAttribute) -> dict[str, Any]:
    return {
        "id": str(attribute.id),
        "character_name": attribute.character_name,
        "attribute_key": attribute.attribute_key,
        "value": attribute.value,
        "unit": attribute.unit,
        "scope": attribute.scope,
        "metadata": attribute.extra_metadata,
    }


def inventory_item_payload(item: InventoryItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "owner_name": item.owner_name,
        "item_name": item.item_name,
        "quantity": item.quantity,
        "unit": item.unit,
        "location_name": item.location_name,
        "description": item.description,
        "metadata": item.extra_metadata,
    }


def map_location_payload(location: MapLocation) -> dict[str, Any]:
    return {
        "id": str(location.id),
        "name": location.name,
        "location_type": location.location_type,
        "summary": location.summary,
        "parent_name": location.parent_name,
        "coordinates": location.coordinates,
        "adjacent_location_names": location.adjacent_location_names,
        "metadata": location.extra_metadata,
    }


RUBRIC_DETAIL_LABELS = {
    "hook": "钩子与追读",
    "progress": "情节推进与因果逻辑",
    "character": "人物选择与情绪代价",
    "conflict": "冲突爽点与压迫感",
    "language_originality": "语言质量与原创细节",
}


def _clamp_score(value: float) -> float:
    return round(min(2.0, max(0.0, value)), 1)


def _count_any(text: str, words: tuple[str, ...]) -> int:
    return sum(text.count(word) for word in words)


def _score_chapter_text(*, node_id: UUID, title: str, text: str) -> dict[str, Any]:
    compact = "".join(text.split())
    char_count = len(compact)
    paragraph_count = len([part for part in text.splitlines() if part.strip()]) or 1
    reasons: list[str] = []
    suggestions: list[str] = []

    opening = compact[:180]
    ending = compact[-220:]
    hook = 1.0
    if any(marker in opening for marker in ("倒计时", "警报", "血", "死", "裂缝", "敌", "失踪", "爆炸", "第一天")):
        hook += 0.4
    if any(marker in ending for marker in ("来了", "失踪", "开门", "带回来", "亮起", "逼近", "完", "终")):
        hook += 0.3
    if char_count < 2500:
        hook -= 0.2
        reasons.append("章节体量偏短，单章承载的追读钩子容易不足。")
        suggestions.append("补一个明确的章末问题、危机或人物选择。")

    action_count = _count_any(compact, ("走", "冲", "斩", "杀", "退", "问", "说", "看", "醒", "选择", "决定", "撤"))
    progress = 1.0 + min(0.6, action_count / 24)
    if any(marker in compact for marker in ("目标", "计划", "任务", "撤", "破阵", "训练", "增援", "觉醒")):
        progress += 0.2
    if char_count < 2200:
        progress -= 0.3
    if progress < 1.3:
        reasons.append("情节推进偏功能化，章内事件增量不够明显。")
        suggestions.append("让本章至少完成一个不可回退的情节变化。")

    character_signal = _count_any(compact, ("叶尘", "苏念", "王磊", "袁晓乐", "林瑶", "江若溪", "秦上士"))
    emotion_signal = _count_any(compact, ("怕", "疼", "沉默", "笑", "哭", "颤", "代价", "选择", "后悔", "相信"))
    character = 0.9 + min(0.5, character_signal / 30) + min(0.4, emotion_signal / 12)
    if emotion_signal < 2:
        character -= 0.2
        reasons.append("人物情绪和选择代价偏少，角色容易变成功能位。")
        suggestions.append("增加一个角色主动选择、犹豫或承担后果的场景。")

    conflict_signal = _count_any(compact, ("敌", "战", "杀", "血", "伤", "死", "裂缝", "妖兽", "赤血", "D级", "E级", "F级", "危机"))
    conflict = 0.9 + min(0.8, conflict_signal / 26)
    if any(marker in compact for marker in ("追", "围", "断后", "塌", "失踪", "领主", "Boss")):
        conflict += 0.2
    if conflict < 1.3:
        reasons.append("单章对抗不够尖锐，读者可能觉得是过渡章。")
        suggestions.append("给本章增加更具体的阻力、失败风险或反转。")

    contrast_count = compact.count("不是")
    no_count = compact.count("没有")
    system_count = _count_any(compact, ("系统", "面板", "F级", "E级", "D级", "星"))
    language = 1.6
    if contrast_count >= 18:
        language -= 0.35
        reasons.append("“不是……”类解释句偏密，容易形成 AI 句式感。")
        suggestions.append("把直接对照改成动作、感官细节、代价或对话潜台词。")
    if no_count >= 18:
        language -= 0.2
    if system_count >= 45:
        language -= 0.35
        reasons.append("系统数字和等级说明偏密，原创场景细节被压缩。")
        suggestions.append("减少面板播报，把等级差转化为可见的身体压力和战术变化。")
    if paragraph_count > 180:
        language -= 0.15
        reasons.append("短段落过密，连续阅读会有机械切分感。")
    if char_count > 5500:
        language -= 0.25
        reasons.append("章节偏长，信息和战斗可能压成一章导致疲劳。")
        suggestions.append("拆分或压缩说明，把高潮保留在更清晰的单章结构里。")
    if char_count < 2400:
        language -= 0.2
    if not reasons:
        reasons.append("章节阅读效果稳定，平台低质风险较低。")
    if not suggestions:
        suggestions.append("保留现有结构，二修时只压缩重复说明。")

    details = {
        "hook": _clamp_score(hook),
        "progress": _clamp_score(progress),
        "character": _clamp_score(character),
        "conflict": _clamp_score(conflict),
        "language_originality": _clamp_score(language),
    }
    total_score = round(sum(details.values()), 1)
    if total_score < 6.5 or details["language_originality"] <= 0.8:
        platform_risk = "高"
    elif total_score < 7.3 or any("AI" in reason or "功能" in reason for reason in reasons):
        platform_risk = "中"
    else:
        platform_risk = "低"

    return {
        "node_id": str(node_id),
        "chapter_title": title,
        "total_score": total_score,
        "platform_risk": platform_risk,
        "details": details,
        "detail_labels": RUBRIC_DETAIL_LABELS,
        "reasons": reasons[:4],
        "suggestions": suggestions[:4],
        "stats": {
            "chars": char_count,
            "paragraphs": paragraph_count,
            "contrast_count": contrast_count,
            "system_count": system_count,
        },
    }


def build_runtime_tools(
    session: AsyncSession,
    *,
    model_profile: ModelProfile | None,
    owner_id: UUID | None = None,
    novel_id: UUID | None = None,
    document_id: UUID | None = None,
) -> list[BaseTool]:
    def scoped_ids() -> tuple[UUID, UUID] | None:
        if owner_id is None or novel_id is None:
            return None
        return owner_id, novel_id

    def current_novel_id(requested_novel_id: str | None = None) -> UUID:
        if novel_id is not None:
            return novel_id
        if requested_novel_id is None:
            raise ValueError("工具缺少当前小说 ID。")
        return UUID(requested_novel_id)

    def current_document_id(requested_document_id: str | None = None) -> UUID:
        if requested_document_id:
            return UUID(requested_document_id)
        if document_id is None:
            raise ValueError("工具缺少当前打开的章节 ID。")
        return document_id

    @tool("search_memory", args_schema=SearchMemoryArgs)
    async def search_memory_runtime(novel_id: str | None = None, query: str = "", limit: int = 8) -> dict[str, Any]:
        """Search approved novel memory items."""
        try:
            resolved_novel_id = current_novel_id(novel_id)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        results = await search_memory_items(session, novel_id=resolved_novel_id, query=query, limit=limit)
        return {"status": "ok", "results": results}

    @tool("search_rag", args_schema=SearchRagArgs)
    async def search_rag_runtime(novel_id: str | None = None, query: str = "", limit: int = 8) -> dict[str, Any]:
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

    @tool("search_documents_by_keyword", args_schema=SearchDocumentsByKeywordArgs)
    async def search_documents_by_keyword_runtime(
        novel_id: str | None = None, query: str = "", limit: int = 20
    ) -> dict[str, Any]:
        """Search chapter titles and bodies by exact keyword or phrase."""
        try:
            resolved_novel_id = current_novel_id(novel_id)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        results = await search_novel_documents(
            session,
            novel_id=resolved_novel_id,
            query=query,
            limit=limit,
        )
        return {"status": "ok", "query": query, "results": results}

    @tool("global_replace_keyword", args_schema=GlobalReplaceKeywordArgs)
    async def global_replace_keyword_runtime(
        old_text: str,
        new_text: str,
        dry_run: bool = True,
        scopes: list[str] | None = None,
        max_occurrences: int = 200,
    ) -> dict[str, Any]:
        """Preview or apply exact keyword replacement across the current novel."""
        scope = scoped_ids()
        if scope is None:
            return {"status": "error", "message": "工具缺少当前用户或小说作用域。"}
        return await global_replace_keyword(
            session,
            novel_id=scope[1],
            old_text=old_text,
            new_text=new_text,
            dry_run=dry_run,
            scopes=scopes,
            max_occurrences=max_occurrences,
            model_profile=model_profile,
        )

    @tool("read_document", args_schema=ReadDocumentArgs)
    async def read_document_runtime(document_id: str | None = None) -> dict[str, Any]:
        """Read a document by id."""
        try:
            resolved_document_id = current_document_id(document_id)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        scope = scoped_ids()
        if scope is None:
            document = await session.scalar(select(Document).where(Document.id == resolved_document_id))
        else:
            try:
                document = await get_owned_document(
                    session,
                    owner_id=scope[0],
                    novel_id=scope[1],
                    document_id=resolved_document_id,
                )
            except Exception:
                document = None
        if document is None:
            return {"status": "error", "message": "文档不存在。"}
        return {
            "status": "ok",
            "document_id": str(resolved_document_id),
            "content": extract_text_from_prosemirror(document.content),
        }

    @tool("propose_document_update", args_schema=ProposeDocumentUpdateArgs)
    async def propose_document_update_runtime(document_id: str | None = None, content: str = "") -> dict[str, Any]:
        """Propose a full chapter body replacement; user must confirm before it applies."""
        scope = scoped_ids()
        if scope is None:
            return {"status": "error", "message": "工具缺少当前用户或小说作用域。"}
        try:
            resolved_document_id = current_document_id(document_id)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        try:
            confirmation = await create_document_update_proposal(
                session,
                owner_id=scope[0],
                novel_id=scope[1],
                document_id=resolved_document_id,
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
    async def write_document_content_runtime(document_id: str | None = None, content: str = "") -> dict[str, Any]:
        """Atomically replace a chapter body and save immediately without confirmation."""
        scope = scoped_ids()
        if scope is None:
            return {"status": "error", "message": "工具缺少当前用户或小说作用域。"}
        try:
            resolved_document_id = current_document_id(document_id)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        try:
            result = await write_document_content(
                session,
                owner_id=scope[0],
                novel_id=scope[1],
                document_id=resolved_document_id,
                content=content,
            )
        except Exception as exc:
            return {"status": "error", "message": getattr(exc, "detail", str(exc))}
        return result

    @tool("propose_selection_replace", args_schema=ProposeSelectionReplaceArgs)
    async def propose_selection_replace_runtime(
        document_id: str | None = None, selected_text: str = "", replacement_text: str = ""
    ) -> dict[str, Any]:
        """Propose replacing one unique text selection after user confirmation."""
        scope = scoped_ids()
        if scope is None:
            return {"status": "error", "message": "工具缺少当前用户或小说作用域。"}
        try:
            resolved_document_id = current_document_id(document_id)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        try:
            confirmation = await create_selection_replace_proposal(
                session,
                owner_id=scope[0],
                novel_id=scope[1],
                document_id=resolved_document_id,
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
    async def list_document_versions_runtime(document_id: str | None = None) -> dict[str, Any]:
        """List saved versions for a document in the current novel."""
        scope = scoped_ids()
        if scope is None:
            return {"status": "error", "message": "工具缺少当前用户或小说作用域。"}
        try:
            resolved_document_id = current_document_id(document_id)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        try:
            versions = await list_owned_document_versions(
                session,
                owner_id=scope[0],
                novel_id=scope[1],
                document_id=resolved_document_id,
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
    async def propose_version_restore_runtime(document_id: str | None = None, version_id: str = "") -> dict[str, Any]:
        """Propose restoring a saved document version after user confirmation."""
        scope = scoped_ids()
        if scope is None:
            return {"status": "error", "message": "工具缺少当前用户或小说作用域。"}
        try:
            resolved_document_id = current_document_id(document_id)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        try:
            confirmation = await create_version_restore_proposal(
                session,
                owner_id=scope[0],
                novel_id=scope[1],
                document_id=resolved_document_id,
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

    @tool("delete_memory_item", args_schema=DeleteMemoryItemArgs)
    async def delete_memory_item_runtime(memory_item_id: str) -> dict[str, Any]:
        """Delete one approved memory item from the current novel."""
        scope = scoped_ids()
        if scope is None:
            return {"status": "error", "message": "工具缺少当前用户或小说作用域。"}
        memory_uuid = UUID(memory_item_id)
        memory = await session.scalar(
            select(MemoryItem).where(MemoryItem.id == memory_uuid, MemoryItem.novel_id == scope[1])
        )
        if memory is None:
            return {"status": "error", "message": "记忆不存在。"}
        deleted = await delete_memory_item_service(
            session,
            owner_id=scope[0],
            item_id=memory_uuid,
        )
        if not deleted:
            return {"status": "error", "message": "记忆不存在。"}
        await session.commit()
        return {
            "status": "ok",
            "action_type": "delete_memory_item",
            "message": "已删除记忆。",
            "memory_item_id": memory_item_id,
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

    @tool("list_character_attributes", args_schema=ListCharacterAttributesArgs)
    async def list_character_attributes_runtime(
        novel_id: str | None = None,
        character_name: str | None = None,
        scope: str | None = None,
    ) -> dict[str, Any]:
        """List structured character attributes for calculation and continuity."""
        attributes = await list_character_attributes(
            session,
            novel_id=current_novel_id(novel_id),
            character_name=character_name,
            scope=scope,
        )
        return {"status": "ok", "attributes": [character_attribute_payload(attribute) for attribute in attributes]}

    @tool("upsert_character_attribute", args_schema=UpsertCharacterAttributeArgs)
    async def upsert_character_attribute_runtime(
        novel_id: str | None = None,
        character_name: str = "",
        attribute_key: str = "",
        value: Any = None,
        unit: str = "",
        scope: str = "current",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create or update one structured character attribute."""
        attribute = await upsert_character_attribute(
            session,
            novel_id=current_novel_id(novel_id),
            character_name=character_name,
            attribute_key=attribute_key,
            value=value,
            unit=unit,
            scope=scope,
            metadata=metadata,
            actor_source="agent",
        )
        await session.commit()
        return {
            "status": "ok",
            "action_type": "upsert_character_attribute",
            "message": f"已记录角色「{attribute.character_name}」属性 {attribute.attribute_key}。",
            **character_attribute_payload(attribute),
        }

    @tool("delete_character_attribute", args_schema=DeleteCharacterAttributeArgs)
    async def delete_character_attribute_runtime(novel_id: str | None = None, attribute_id: str = "") -> dict[str, Any]:
        """Delete a structured character attribute by id."""
        deleted = await delete_character_attribute(
            session,
            novel_id=current_novel_id(novel_id),
            attribute_id=UUID(attribute_id),
            actor_source="agent",
        )
        if not deleted:
            return {"status": "error", "message": "角色属性不存在。"}
        await session.commit()
        return {
            "status": "ok",
            "action_type": "delete_character_attribute",
            "message": "已删除角色属性。",
            "id": attribute_id,
        }

    @tool("list_inventory_items", args_schema=ListInventoryItemsArgs)
    async def list_inventory_items_runtime(
        novel_id: str | None = None,
        owner_name: str | None = None,
        location_name: str | None = None,
    ) -> dict[str, Any]:
        """List structured inventory items with calculable quantities."""
        items = await list_inventory_items(
            session,
            novel_id=current_novel_id(novel_id),
            owner_name=owner_name,
            location_name=location_name,
        )
        return {"status": "ok", "items": [inventory_item_payload(item) for item in items]}

    @tool("upsert_inventory_item", args_schema=UpsertInventoryItemArgs)
    async def upsert_inventory_item_runtime(
        novel_id: str | None = None,
        owner_name: str = "",
        item_name: str = "",
        quantity: float = 0,
        unit: str = "",
        location_name: str | None = None,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create or update one inventory item. Same owner+item+location upserts."""
        item = await upsert_inventory_item(
            session,
            novel_id=current_novel_id(novel_id),
            owner_name=owner_name,
            item_name=item_name,
            quantity=quantity,
            unit=unit,
            location_name=location_name,
            description=description,
            metadata=metadata,
            actor_source="agent",
        )
        await session.commit()
        return {
            "status": "ok",
            "action_type": "upsert_inventory_item",
            "message": f"已记录「{item.owner_name}」背包物品「{item.item_name}」。",
            **inventory_item_payload(item),
        }

    @tool("delete_inventory_item", args_schema=DeleteInventoryItemArgs)
    async def delete_inventory_item_runtime(novel_id: str | None = None, item_id: str = "") -> dict[str, Any]:
        """Delete an inventory item by id."""
        deleted = await delete_inventory_item(
            session,
            novel_id=current_novel_id(novel_id),
            item_id=UUID(item_id),
            actor_source="agent",
        )
        if not deleted:
            return {"status": "error", "message": "背包物品不存在。"}
        await session.commit()
        return {
            "status": "ok",
            "action_type": "delete_inventory_item",
            "message": "已删除背包物品。",
            "id": item_id,
        }

    @tool("list_map_locations", args_schema=ListMapLocationsArgs)
    async def list_map_locations_runtime(
        novel_id: str | None = None,
        location_type: str | None = None,
        parent_name: str | None = None,
    ) -> dict[str, Any]:
        """List structured map locations, regions, coordinates, and adjacency."""
        locations = await list_map_locations(
            session,
            novel_id=current_novel_id(novel_id),
            location_type=location_type,
            parent_name=parent_name,
        )
        return {"status": "ok", "locations": [map_location_payload(location) for location in locations]}

    @tool("upsert_map_location", args_schema=UpsertMapLocationArgs)
    async def upsert_map_location_runtime(
        novel_id: str | None = None,
        name: str = "",
        location_type: str = "location",
        summary: str = "",
        parent_name: str | None = None,
        coordinates: dict[str, Any] | None = None,
        adjacent_location_names: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create or update one structured map location."""
        location = await upsert_map_location(
            session,
            novel_id=current_novel_id(novel_id),
            name=name,
            location_type=location_type,
            summary=summary,
            parent_name=parent_name,
            coordinates=coordinates,
            adjacent_location_names=adjacent_location_names,
            metadata=metadata,
            actor_source="agent",
        )
        await session.commit()
        return {
            "status": "ok",
            "action_type": "upsert_map_location",
            "message": f"已记录地图地点「{location.name}」。",
            **map_location_payload(location),
        }

    @tool("delete_map_location", args_schema=DeleteMapLocationArgs)
    async def delete_map_location_runtime(novel_id: str | None = None, location_id: str = "") -> dict[str, Any]:
        """Delete a map location by id."""
        deleted = await delete_map_location(
            session,
            novel_id=current_novel_id(novel_id),
            location_id=UUID(location_id),
            actor_source="agent",
        )
        if not deleted:
            return {"status": "error", "message": "地图地点不存在。"}
        await session.commit()
        return {
            "status": "ok",
            "action_type": "delete_map_location",
            "message": "已删除地图地点。",
            "id": location_id,
        }

    @tool("create_relationship_edge", args_schema=CreateRelationshipEdgeArgs)
    async def create_relationship_edge_runtime(
        novel_id: str,
        source_character: str,
        target_character: str,
        relationship_type: str,
        description: str = "",
        timeline_event_id: str | None = None,
        timeline_event_time: str | None = None,
        timeline_title: str | None = None,
    ) -> dict[str, Any]:
        """Create a relationship edge between characters."""
        metadata = relationship_timeline_metadata(
            timeline_event_id=timeline_event_id,
            timeline_event_time=timeline_event_time,
            timeline_title=timeline_title,
        )
        edge = await create_relationship_edge(
            session,
            novel_id=current_novel_id(novel_id),
            source_character=source_character,
            target_character=target_character,
            relationship_type=relationship_type,
            description=description,
            metadata=metadata,
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
        timeline_event_id: str | None = None,
        timeline_event_time: str | None = None,
        timeline_title: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing relationship edge by id."""
        metadata = relationship_timeline_metadata(
            timeline_event_id=timeline_event_id,
            timeline_event_time=timeline_event_time,
            timeline_title=timeline_title,
        )
        edge = await update_relationship_edge(
            session,
            novel_id=current_novel_id(novel_id),
            edge_id=UUID(edge_id),
            source_character=source_character,
            target_character=target_character,
            relationship_type=relationship_type,
            description=description,
            metadata=metadata or None,
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

    @tool("score_chapters_with_rubric", args_schema=ScoreChaptersWithRubricArgs)
    async def score_chapters_with_rubric_runtime(
        novel_id: str | None = None,
        scope: str = "all",
        node_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Score selected or all chapters with a 10-point platform quality rubric."""
        try:
            resolved_novel_id = current_novel_id(novel_id)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        selected_node_ids = [UUID(node_id) for node_id in (node_ids or [])]
        stmt = (
            select(WorkspaceNode, Document)
            .join(Document, Document.id == WorkspaceNode.document_id)
            .where(
                WorkspaceNode.novel_id == resolved_novel_id,
                WorkspaceNode.node_type == "chapter",
                WorkspaceNode.status != "trashed",
            )
        )
        if selected_node_ids:
            stmt = stmt.where(WorkspaceNode.id.in_(selected_node_ids))
        rows = (await session.execute(stmt)).all()
        parent_ids = {node.parent_id for node, _document in rows if node.parent_id is not None}
        parent_positions: dict[UUID, int] = {}
        if parent_ids:
            parent_rows = await session.execute(
                select(WorkspaceNode.id, WorkspaceNode.position).where(WorkspaceNode.id.in_(parent_ids))
            )
            parent_positions = {row.id: row.position for row in parent_rows}
        ordered_rows = sorted(
            rows,
            key=lambda row: (
                parent_positions.get(row[0].parent_id, -1) if row[0].parent_id is not None else -1,
                row[0].position,
                row[0].created_at,
            ),
        )
        scores = [
            _score_chapter_text(
                node_id=node.id,
                title=node.title,
                text=extract_text_from_prosemirror(document.content),
            )
            for node, document in ordered_rows
        ]
        average_score = round(sum(score["total_score"] for score in scores) / len(scores), 1) if scores else 0
        return {
            "status": "ok",
            "rubric": {
                "total_points": 10,
                "details": RUBRIC_DETAIL_LABELS,
                "platform_checks": [
                    "粗制滥造风险",
                    "AI批量生成感",
                    "逻辑与因果完整性",
                    "语言原创细节",
                    "低质功能章连续出现风险",
                ],
            },
            "summary": {"chapter_count": len(scores), "average_score": average_score},
            "scores": scores,
        }

    @tool("propose_rewrite", args_schema=ProposeRewriteArgs)
    async def propose_rewrite_runtime(
        document_id: str | None = None, selected_text: str = "", instruction: str = ""
    ) -> dict[str, Any]:
        """Draft a rewrite proposal without mutating the document."""
        try:
            resolved_document_id = current_document_id(document_id)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        scope = scoped_ids()
        if scope is not None:
            replacement_text = draft_rewrite(selected_text, instruction)
            try:
                confirmation = await create_selection_replace_proposal(
                    session,
                    owner_id=scope[0],
                    novel_id=scope[1],
                    document_id=resolved_document_id,
                    selected_text=selected_text,
                    replacement_text=replacement_text,
                    action_type="rewrite_selection",
                )
                return {
                    "status": "ok",
                    "action_type": "confirmation_created",
                    "confirmation_id": str(confirmation.id),
                    "message": "我已草拟改写方案，请确认后再应用。",
                }
            except Exception:
                return {
                    "action_type": "rewrite_selection",
                    "message": "我已草拟改写方案，请确认后再应用。",
                    "payload": {
                        "document_id": str(resolved_document_id),
                        "selected_text": selected_text,
                        "replacement_text": replacement_text,
                    },
                }
        return {
            "action_type": "rewrite_selection",
            "message": "我已草拟改写方案，请确认后再应用。",
            "payload": {
                "document_id": str(resolved_document_id),
                "selected_text": selected_text,
                "replacement_text": draft_rewrite(selected_text, instruction),
            },
        }

    runtime_by_name = {
        "search_memory": search_memory_runtime,
        "search_rag": search_rag_runtime,
        "search_documents_by_keyword": search_documents_by_keyword_runtime,
        "global_replace_keyword": global_replace_keyword_runtime,
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
        "delete_memory_item": delete_memory_item_runtime,
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
        "list_character_attributes": list_character_attributes_runtime,
        "upsert_character_attribute": upsert_character_attribute_runtime,
        "delete_character_attribute": delete_character_attribute_runtime,
        "list_inventory_items": list_inventory_items_runtime,
        "upsert_inventory_item": upsert_inventory_item_runtime,
        "delete_inventory_item": delete_inventory_item_runtime,
        "list_map_locations": list_map_locations_runtime,
        "upsert_map_location": upsert_map_location_runtime,
        "delete_map_location": delete_map_location_runtime,
        "create_relationship_edge": create_relationship_edge_runtime,
        "update_relationship_edge": update_relationship_edge_runtime,
        "delete_relationship_edge": delete_relationship_edge_runtime,
        "list_material_changes": list_material_changes_runtime,
        "score_chapters_with_rubric": score_chapters_with_rubric_runtime,
        "propose_rewrite": propose_rewrite_runtime,
    }

    tools: list[BaseTool] = []
    for tool_obj in get_agent_tools():
        tools.append(runtime_by_name.get(tool_obj.name, tool_obj))
    return tools
