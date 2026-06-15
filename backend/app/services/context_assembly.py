from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import ContextBudget, ContextItem, ContextPack, build_context_pack, estimate_tokens
from app.models import (
    CharacterState,
    ContextPack as ContextPackRecord,
    ContextSnapshot,
    CreativeAsset,
    Document,
    MemoryItem,
    Message,
    ModelProfile,
    Novel,
    RelationshipEdge,
    TimelineEvent,
    WorkspaceNode,
)
from app.schemas.context import ContextDetail, ContextDetailItem
from app.services.context_settings import get_or_create_context_settings
from app.services.rag import extract_text_from_prosemirror, get_embedding_model_profile, index_text, search_rag_chunks


@dataclass
class AssembledContext:
    pack: ContextPack
    context_detail: ContextDetail
    status_messages: list[str]
    history_messages: list[BaseMessage]


def _build_status_messages(pack: ContextPack, *, compressed_sources: set[str], snapshot_created: bool) -> list[str]:
    messages = [f"上下文占用约 {round(pack.usage_ratio * 100)}%。"]
    if any(item.source == "neighboring_chapter" for item in pack.items):
        messages.append("已包含相邻章节上下文。")
    if any(item.source == "key_memory" for item in pack.items):
        messages.append("已加载关键记忆。")
    if any(item.source == "rag_result" for item in pack.items):
        messages.append("已包含 RAG 检索结果。")
    if pack.usage_ratio >= 0.7:
        messages.append("上下文接近上限，可能即将压缩。")
    if compressed_sources:
        messages.append(f"已自动压缩：{', '.join(sorted(compressed_sources))}。")
    if snapshot_created:
        messages.append("已生成上下文快照并继续对话。")
    return messages


def _detail_from_pack(pack: ContextPack, *, compressed_sources: set[str], snapshot_id: UUID | None) -> ContextDetail:
    warnings: list[str] = []
    if pack.usage_ratio >= 0.7:
        warnings.append("上下文占用较高")
    if compressed_sources:
        warnings.append("部分来源已自动压缩")
    return ContextDetail(
        usage_ratio=pack.usage_ratio,
        items=[
            ContextDetailItem(
                source=item.source,
                tokens=item.estimated_tokens,
                compressed=item.source in compressed_sources,
            )
            for item in pack.items
        ],
        warnings=warnings,
        snapshot_id=snapshot_id,
    )


def _truncate_text(text: str, max_tokens: int) -> str:
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"


def _compress_pack(pack: ContextPack, budget: ContextBudget) -> tuple[ContextPack, set[str]]:
    compressed: set[str] = set()
    available = max(0, budget.max_tokens - budget.response_tokens)
    target_tokens = int(available * 0.84)

    items = list(pack.items)
    order = ["conversation_history", "rag_result", "neighboring_chapter", "structured_memory"]

    def total_tokens() -> int:
        return sum(item.estimated_tokens for item in items)

    for source in order:
        if total_tokens() <= target_tokens:
            break
        for index, item in enumerate(items):
            if item.source != source:
                continue
            if source == "conversation_history":
                shortened = _truncate_text(item.text, max(50, item.estimated_tokens // 2))
            elif source == "rag_result":
                shortened = _truncate_text(item.text, max(40, item.estimated_tokens // 2))
            elif source == "neighboring_chapter":
                shortened = _truncate_text(item.text, max(60, item.estimated_tokens // 3))
            else:
                shortened = _truncate_text(item.text, max(40, item.estimated_tokens // 2))
            items[index] = ContextItem(
                source=item.source,
                text=shortened,
                priority=item.priority,
                estimated_tokens=estimate_tokens(shortened),
            )
            compressed.add(source)

    usage_ratio = total_tokens() / budget.max_tokens if budget.max_tokens else 1
    return (
        ContextPack(
            items=items,
            estimated_tokens=total_tokens(),
            usage_ratio=usage_ratio,
            status_messages=pack.status_messages,
        ),
        compressed,
    )


async def _create_context_snapshot(
    session: AsyncSession,
    *,
    novel_id: UUID,
    conversation_id: UUID,
    pack: ContextPack,
    user_message: str,
) -> ContextSnapshot:
    facts = {
        "open_questions": [],
        "recent_goal": user_message,
        "included_sources": [item.source for item in pack.items],
    }
    summary = f"对话上下文快照：{user_message[:200]}"
    snapshot = ContextSnapshot(
        novel_id=novel_id,
        conversation_id=conversation_id,
        summary=summary,
        facts=facts,
        created_at=datetime.now(UTC),
    )
    session.add(snapshot)
    await session.flush()

    memory = MemoryItem(
        novel_id=novel_id,
        memory_type="context_snapshot",
        title=f"上下文快照 {snapshot.id.hex[:8]}",
        body=summary,
        importance=70,
        extra_metadata={"snapshot_id": str(snapshot.id)},
        created_at=datetime.now(UTC),
    )
    session.add(memory)
    await session.flush()

    novel = await session.scalar(select(Novel).where(Novel.id == novel_id))
    model_profile = await get_embedding_model_profile(session, novel) if novel else None
    await index_text(
        session,
        novel_id=novel_id,
        source_type="context_snapshot",
        source_id=str(snapshot.id),
        text=summary,
        model_profile=model_profile,
    )
    await session.commit()
    await session.refresh(snapshot)
    return snapshot


async def _load_document_text(session: AsyncSession, document_id: UUID | None) -> str:
    if document_id is None:
        return ""
    document = await session.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        return ""
    return extract_text_from_prosemirror(document.content)


async def _load_key_memories(session: AsyncSession, novel_id: UUID) -> list[str]:
    items = await session.scalars(
        select(MemoryItem)
        .where(
            MemoryItem.novel_id == novel_id,
            MemoryItem.memory_type.in_(("key_memory", "context_snapshot")),
        )
        .order_by(MemoryItem.importance.desc(), MemoryItem.created_at.desc())
        .limit(12)
    )
    return [f"{item.title}：{item.body}" for item in items]


async def _load_structured_assets(session: AsyncSession, novel_id: UUID) -> list[str]:
    assets = await session.scalars(select(CreativeAsset).where(CreativeAsset.novel_id == novel_id).limit(8))
    states = await session.scalars(select(CharacterState).where(CharacterState.novel_id == novel_id).limit(8))
    events = await session.scalars(select(TimelineEvent).where(TimelineEvent.novel_id == novel_id).limit(8))
    relationships = await session.scalars(
        select(RelationshipEdge).where(RelationshipEdge.novel_id == novel_id).limit(8)
    )
    lines: list[str] = []
    lines.extend(f"素材 {item.name}：{item.summary}" for item in assets)
    lines.extend(f"角色状态 {item.character_name}：{item.state}" for item in states)
    lines.extend(f"时间线 {item.title}：{item.summary}" for item in events)
    lines.extend(
        f"人物关系 {item.source_character} {item.relationship_type} {item.target_character}：{item.description}"
        for item in relationships
    )
    return lines


async def _load_neighboring_chapters(
    session: AsyncSession,
    *,
    novel_id: UUID,
    document_id: UUID | None,
    count: int,
) -> list[str]:
    nodes = list(
        await session.scalars(
            select(WorkspaceNode)
            .where(
                WorkspaceNode.novel_id == novel_id,
                WorkspaceNode.node_type == "chapter",
                WorkspaceNode.status != "trashed",
            )
            .order_by(WorkspaceNode.position, WorkspaceNode.id)
        )
    )
    if not nodes:
        return []

    current_index = None
    if document_id is not None:
        for index, node in enumerate(nodes):
            if node.document_id == document_id:
                current_index = index
                break

    if current_index is None:
        selected = nodes[-count:]
    else:
        start = max(0, current_index - count + 1)
        selected = nodes[start : current_index + 1]

    results: list[str] = []
    for node in selected:
        if node.document_id is None:
            continue
        document = await session.scalar(select(Document).where(Document.id == node.document_id))
        if document is None:
            continue
        text = extract_text_from_prosemirror(document.content)
        if text:
            results.append(f"《{node.title}》\n{text}")
    return results


async def _load_conversation_history(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    limit: int,
) -> tuple[list[str], list[BaseMessage]]:
    messages = list(
        await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
    )
    messages.reverse()
    if messages and messages[-1].role == "user":
        messages = messages[:-1]

    history_lines: list[str] = []
    history_messages: list[BaseMessage] = []
    for item in messages[-20:]:
        if item.role == "user":
            history_lines.append(f"用户：{item.content}")
            history_messages.append(HumanMessage(content=item.content))
        elif item.role == "assistant":
            history_lines.append(f"助手：{item.content}")
            reasoning_content = item.extra_metadata.get("reasoning_content")
            additional_kwargs = (
                {"reasoning_content": reasoning_content}
                if isinstance(reasoning_content, str)
                else {}
            )
            history_messages.append(AIMessage(content=item.content, additional_kwargs=additional_kwargs))

    return history_lines, history_messages[-10:]


async def assemble_context(
    session: AsyncSession,
    *,
    novel: Novel,
    conversation_id: UUID,
    document_id: UUID | None,
    selected_text: str | None,
    user_message: str,
    model_profile: ModelProfile | None,
    message_id: UUID | None = None,
) -> AssembledContext:
    settings = await get_or_create_context_settings(session, novel=novel)
    sources = settings.sources
    budget_settings = settings.budget

    max_tokens = int(budget_settings.get("max_context_tokens", 8000))
    response_reserve = int(budget_settings.get("response_reserve", 1000))
    budget = ContextBudget(max_tokens=max_tokens, response_tokens=response_reserve)

    current_document = ""
    if sources.get("current_document", True):
        current_document = await _load_document_text(session, document_id)

    key_memories: list[str] = []
    if sources.get("key_memories", True):
        key_memories = await _load_key_memories(session, novel.id)

    structured: list[str] = []
    if sources.get("structured_assets", True):
        structured = await _load_structured_assets(session, novel.id)

    neighbors: list[str] = []
    if sources.get("neighboring_chapters", True):
        neighbors = await _load_neighboring_chapters(
            session,
            novel_id=novel.id,
            document_id=document_id,
            count=int(budget_settings.get("recent_chapters_count", 3)),
        )

    rag_results: list[str] = []
    if sources.get("rag_search", True):
        try:
            chunks = await search_rag_chunks(
                session,
                novel_id=novel.id,
                query=user_message,
                limit=8,
                model_profile=model_profile,
                excluded_source_types={
                    "character_state",
                    "creative_asset",
                    "relationship_edge",
                    "timeline_event",
                },
            )
            rag_results = [chunk.text for chunk in chunks]
        except Exception:
            rag_results = []

    conversation_lines: list[str] = []
    history_messages: list[BaseMessage] = []
    if sources.get("conversation_history", True):
        conversation_lines, history_messages = await _load_conversation_history(
            session,
            conversation_id=conversation_id,
            limit=int(budget_settings.get("conversation_history_limit", 20)),
        )

    pack = build_context_pack(
        user_instruction=user_message,
        current_document_text=current_document,
        selected_text=selected_text if sources.get("selected_text", True) else None,
        key_memories=key_memories,
        structured_memories=structured,
        neighboring_chapters=neighbors,
        rag_results=rag_results,
        conversation_histories=conversation_lines,
        budget=budget,
    )

    compressed_sources: set[str] = set()
    snapshot_id: UUID | None = None

    if pack.usage_ratio >= 0.95:
        snapshot = await _create_context_snapshot(
            session,
            novel_id=novel.id,
            conversation_id=conversation_id,
            pack=pack,
            user_message=user_message,
        )
        snapshot_id = snapshot.id
        snapshot_text = f"上下文快照：{snapshot.summary}"
        pack = build_context_pack(
            user_instruction=user_message,
            current_document_text=current_document,
            selected_text=selected_text if sources.get("selected_text", True) else None,
            key_memories=[snapshot_text, *key_memories[:3]],
            structured_memories=structured[:2],
            neighboring_chapters=[],
            rag_results=[],
            conversation_histories=conversation_lines[-4:],
            budget=budget,
        )
        compressed_sources.update({"rag_result", "neighboring_chapter", "structured_memory"})
    elif pack.usage_ratio >= 0.85:
        pack, compressed_sources = _compress_pack(pack, budget)

    status_messages = _build_status_messages(
        pack,
        compressed_sources=compressed_sources,
        snapshot_created=snapshot_id is not None,
    )
    context_detail = _detail_from_pack(pack, compressed_sources=compressed_sources, snapshot_id=snapshot_id)

    record = ContextPackRecord(
        conversation_id=conversation_id,
        message_id=message_id,
        items=[
            {"source": item.source, "tokens": item.estimated_tokens, "compressed": item.source in compressed_sources}
            for item in pack.items
        ],
        usage_ratio=pack.usage_ratio,
        created_at=datetime.now(UTC),
    )
    session.add(record)
    await session.commit()

    return AssembledContext(
        pack=ContextPack(
            items=pack.items,
            estimated_tokens=pack.estimated_tokens,
            usage_ratio=pack.usage_ratio,
            status_messages=status_messages,
        ),
        context_detail=context_detail,
        status_messages=status_messages,
        history_messages=history_messages,
    )
