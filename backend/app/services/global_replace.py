from copy import deepcopy
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CharacterState,
    CreativeAsset,
    Document,
    DocumentVersion,
    MemoryItem,
    ModelProfile,
    RelationshipEdge,
    TimelineEvent,
)
from app.services.rag import extract_text_from_prosemirror, index_text

DEFAULT_REPLACE_SCOPES = (
    "documents",
    "memories",
    "creative_assets",
    "timeline_events",
    "character_states",
    "relationship_edges",
)


def _empty_summary() -> dict[str, dict[str, int]]:
    return {scope: {"items": 0, "occurrences": 0} for scope in DEFAULT_REPLACE_SCOPES}


def _replace_string(value: str, old_text: str, new_text: str) -> tuple[str, int]:
    occurrences = value.count(old_text)
    if occurrences == 0:
        return value, 0
    return value.replace(old_text, new_text), occurrences


def _replace_prosemirror_text(value: Any, old_text: str, new_text: str) -> tuple[Any, int]:
    if isinstance(value, list):
        next_items: list[Any] = []
        total = 0
        for item in value:
            next_item, count = _replace_prosemirror_text(item, old_text, new_text)
            next_items.append(next_item)
            total += count
        return next_items, total
    if not isinstance(value, dict):
        return value, 0

    updated = dict(value)
    total = 0
    text = updated.get("text")
    if isinstance(text, str):
        updated["text"], total = _replace_string(text, old_text, new_text)
    if "content" in updated:
        updated["content"], child_count = _replace_prosemirror_text(updated["content"], old_text, new_text)
        total += child_count
    return updated, total


def _add_match(
    matches: list[dict[str, Any]],
    *,
    source_type: str,
    source_id: UUID,
    field: str,
    occurrences: int,
) -> None:
    if occurrences <= 0 or len(matches) >= 20:
        return
    matches.append(
        {
            "source_type": source_type,
            "source_id": str(source_id),
            "field": field,
            "occurrences": occurrences,
        }
    )


def _record_summary(summary: dict[str, dict[str, int]], scope: str, occurrences: int) -> None:
    if occurrences <= 0:
        return
    summary[scope]["items"] += 1
    summary[scope]["occurrences"] += occurrences


async def global_replace_keyword(
    session: AsyncSession,
    *,
    novel_id: UUID,
    old_text: str,
    new_text: str,
    dry_run: bool = True,
    scopes: list[str] | None = None,
    max_occurrences: int = 200,
    model_profile: ModelProfile | None = None,
) -> dict[str, Any]:
    old_text = old_text.strip()
    if not old_text:
        return {"status": "error", "message": "被替换关键字不能为空。"}
    if old_text == new_text:
        return {"status": "error", "message": "替换前后内容不能相同。"}

    selected_scopes = tuple(scopes or DEFAULT_REPLACE_SCOPES)
    unsupported = sorted(set(selected_scopes) - set(DEFAULT_REPLACE_SCOPES))
    if unsupported:
        return {"status": "error", "message": f"不支持的替换范围：{', '.join(unsupported)}。"}

    summary = _empty_summary()
    matches: list[dict[str, Any]] = []
    documents_to_index: list[Document] = []
    memories_to_index: list[MemoryItem] = []
    assets_to_index: list[CreativeAsset] = []
    events_to_index: list[TimelineEvent] = []
    states_to_index: list[CharacterState] = []
    edges_to_index: list[RelationshipEdge] = []

    if "documents" in selected_scopes:
        documents = list(await session.scalars(select(Document).where(Document.novel_id == novel_id)))
        for document in documents:
            next_content, occurrences = _replace_prosemirror_text(document.content, old_text, new_text)
            _record_summary(summary, "documents", occurrences)
            _add_match(
                matches,
                source_type="document",
                source_id=document.id,
                field="content",
                occurrences=occurrences,
            )
            if occurrences > 0 and not dry_run:
                session.add(DocumentVersion(document_id=document.id, source="agent_global_replace", content=deepcopy(document.content)))
                document.content = next_content
                documents_to_index.append(document)

    if "memories" in selected_scopes:
        memories = list(await session.scalars(select(MemoryItem).where(MemoryItem.novel_id == novel_id)))
        for memory in memories:
            next_title, title_count = _replace_string(memory.title, old_text, new_text)
            next_body, body_count = _replace_string(memory.body, old_text, new_text)
            occurrences = title_count + body_count
            _record_summary(summary, "memories", occurrences)
            _add_match(matches, source_type="memory", source_id=memory.id, field="title", occurrences=title_count)
            _add_match(matches, source_type="memory", source_id=memory.id, field="body", occurrences=body_count)
            if occurrences > 0 and not dry_run:
                memory.title = next_title
                memory.body = next_body
                memories_to_index.append(memory)

    if "creative_assets" in selected_scopes:
        assets = list(await session.scalars(select(CreativeAsset).where(CreativeAsset.novel_id == novel_id)))
        for asset in assets:
            next_name, name_count = _replace_string(asset.name, old_text, new_text)
            next_summary, summary_count = _replace_string(asset.summary, old_text, new_text)
            occurrences = name_count + summary_count
            _record_summary(summary, "creative_assets", occurrences)
            _add_match(matches, source_type="creative_asset", source_id=asset.id, field="name", occurrences=name_count)
            _add_match(
                matches,
                source_type="creative_asset",
                source_id=asset.id,
                field="summary",
                occurrences=summary_count,
            )
            if occurrences > 0 and not dry_run:
                asset.name = next_name
                asset.summary = next_summary
                assets_to_index.append(asset)

    if "timeline_events" in selected_scopes:
        events = list(await session.scalars(select(TimelineEvent).where(TimelineEvent.novel_id == novel_id)))
        for event in events:
            next_title, title_count = _replace_string(event.title, old_text, new_text)
            next_event_time, time_count = _replace_string(event.event_time, old_text, new_text)
            next_summary, summary_count = _replace_string(event.summary, old_text, new_text)
            occurrences = title_count + time_count + summary_count
            _record_summary(summary, "timeline_events", occurrences)
            _add_match(matches, source_type="timeline_event", source_id=event.id, field="title", occurrences=title_count)
            _add_match(
                matches,
                source_type="timeline_event",
                source_id=event.id,
                field="event_time",
                occurrences=time_count,
            )
            _add_match(
                matches,
                source_type="timeline_event",
                source_id=event.id,
                field="summary",
                occurrences=summary_count,
            )
            if occurrences > 0 and not dry_run:
                event.title = next_title
                event.event_time = next_event_time
                event.summary = next_summary
                events_to_index.append(event)

    if "character_states" in selected_scopes:
        states = list(await session.scalars(select(CharacterState).where(CharacterState.novel_id == novel_id)))
        for state in states:
            next_name, name_count = _replace_string(state.character_name, old_text, new_text)
            next_state, state_count = _replace_string(state.state, old_text, new_text)
            next_scope, scope_count = _replace_string(state.scope, old_text, new_text)
            occurrences = name_count + state_count + scope_count
            _record_summary(summary, "character_states", occurrences)
            _add_match(matches, source_type="character_state", source_id=state.id, field="character_name", occurrences=name_count)
            _add_match(matches, source_type="character_state", source_id=state.id, field="state", occurrences=state_count)
            _add_match(matches, source_type="character_state", source_id=state.id, field="scope", occurrences=scope_count)
            if occurrences > 0 and not dry_run:
                state.character_name = next_name
                state.state = next_state
                state.scope = next_scope
                states_to_index.append(state)

    if "relationship_edges" in selected_scopes:
        edges = list(await session.scalars(select(RelationshipEdge).where(RelationshipEdge.novel_id == novel_id)))
        for edge in edges:
            next_source, source_count = _replace_string(edge.source_character, old_text, new_text)
            next_target, target_count = _replace_string(edge.target_character, old_text, new_text)
            next_type, type_count = _replace_string(edge.relationship_type, old_text, new_text)
            next_description, description_count = _replace_string(edge.description, old_text, new_text)
            occurrences = source_count + target_count + type_count + description_count
            _record_summary(summary, "relationship_edges", occurrences)
            _add_match(
                matches,
                source_type="relationship_edge",
                source_id=edge.id,
                field="source_character",
                occurrences=source_count,
            )
            _add_match(
                matches,
                source_type="relationship_edge",
                source_id=edge.id,
                field="target_character",
                occurrences=target_count,
            )
            _add_match(
                matches,
                source_type="relationship_edge",
                source_id=edge.id,
                field="relationship_type",
                occurrences=type_count,
            )
            _add_match(
                matches,
                source_type="relationship_edge",
                source_id=edge.id,
                field="description",
                occurrences=description_count,
            )
            if occurrences > 0 and not dry_run:
                edge.source_character = next_source
                edge.target_character = next_target
                edge.relationship_type = next_type
                edge.description = next_description
                edges_to_index.append(edge)

    total_occurrences = sum(scope["occurrences"] for scope in summary.values())
    if not dry_run and total_occurrences > max_occurrences:
        await session.rollback()
        return {
            "status": "error",
            "message": f"命中 {total_occurrences} 处，超过单次替换上限 {max_occurrences}。",
            "dry_run": dry_run,
            "summary": summary,
            "total_occurrences": total_occurrences,
        }

    if not dry_run and total_occurrences:
        for document in documents_to_index:
            await index_text(
                session,
                novel_id=novel_id,
                source_type="document",
                source_id=str(document.id),
                text=extract_text_from_prosemirror(document.content),
                model_profile=model_profile,
            )
        for memory in memories_to_index:
            await index_text(
                session,
                novel_id=novel_id,
                source_type="memory",
                source_id=str(memory.id),
                text=f"{memory.title}\n{memory.body}",
                model_profile=model_profile,
                metadata={"memory_type": memory.memory_type, "importance": memory.importance},
            )
        for asset in assets_to_index:
            await index_text(
                session,
                novel_id=novel_id,
                source_type="creative_asset",
                source_id=str(asset.id),
                text=f"{asset.asset_type}: {asset.name}\n{asset.summary}",
                model_profile=model_profile,
                metadata={"asset_type": asset.asset_type},
            )
        for event in events_to_index:
            await index_text(
                session,
                novel_id=novel_id,
                source_type="timeline_event",
                source_id=str(event.id),
                text=f"{event.event_time}: {event.title}\n{event.summary}",
                model_profile=model_profile,
            )
        for state in states_to_index:
            await index_text(
                session,
                novel_id=novel_id,
                source_type="character_state",
                source_id=str(state.id),
                text=f"{state.character_name} [{state.scope}]: {state.state}",
                model_profile=model_profile,
            )
        for edge in edges_to_index:
            await index_text(
                session,
                novel_id=novel_id,
                source_type="relationship_edge",
                source_id=str(edge.id),
                text=f"{edge.source_character} {edge.relationship_type} {edge.target_character}: {edge.description}",
                model_profile=model_profile,
            )
        await session.commit()

    return {
        "status": "ok",
        "dry_run": dry_run,
        "old_text": old_text,
        "new_text": new_text,
        "summary": summary,
        "total_occurrences": total_occurrences,
        "matches": matches,
        "message": "已生成全局替换预览。" if dry_run else f"已全局替换 {total_occurrences} 处。",
    }
