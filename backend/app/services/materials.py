import re
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CharacterAttribute,
    CharacterState,
    CreativeAsset,
    InventoryItem,
    MapLocation,
    MaterialChange,
    RagChunk,
    RelationshipEdge,
    TimelineEvent,
)
from app.services.rag import index_text

MaterialActorSource = str  # "user" | "agent"


def _creative_asset_snapshot(asset: CreativeAsset) -> dict[str, Any]:
    return {
        "id": str(asset.id),
        "asset_type": asset.asset_type,
        "name": asset.name,
        "summary": asset.summary,
        "metadata": asset.extra_metadata,
    }


def _timeline_event_snapshot(event: TimelineEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "title": event.title,
        "event_time": event.event_time,
        "summary": event.summary,
        "position": event.position,
        "metadata": event.extra_metadata,
    }


_CN_VOLUME_NUMBERS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _parse_cn_or_digit_number(raw: str) -> int | None:
    if raw.isdigit():
        return int(raw)
    if raw == "十":
        return 10
    if len(raw) == 2 and raw[0] == "十" and raw[1] in _CN_VOLUME_NUMBERS:
        return 10 + _CN_VOLUME_NUMBERS[raw[1]]
    if len(raw) == 2 and raw[0] in _CN_VOLUME_NUMBERS and raw[1] == "十":
        return _CN_VOLUME_NUMBERS[raw[0]] * 10
    return _CN_VOLUME_NUMBERS.get(raw)


def _extract_volume_number(text: str) -> int | None:
    match = re.search(r"第([一二三四五六七八九十\d]+)卷", text)
    if not match:
        return None
    return _parse_cn_or_digit_number(match.group(1))


def _normalize_timeline_label(value: str) -> str:
    return " ".join(value.split())


def _normalize_timeline_summary(summary: str) -> str:
    return " ".join(summary.split())


def _timeline_event_key(title: str, event_time: str) -> tuple[str, str]:
    return (_normalize_timeline_label(title), _normalize_timeline_label(event_time))


def _timeline_heuristic_sort_key(event: TimelineEvent) -> tuple[int, int, str]:
    combined = f"{event.event_time} {event.title}"
    if any(marker in combined for marker in ("故事开始", "开篇", "序章", "起点")):
        return (0, 0, event.created_at.isoformat())

    title_volume = _extract_volume_number(event.title)
    time_volume = _extract_volume_number(event.event_time)
    primary = title_volume if title_volume is not None else (time_volume if time_volume is not None else 999)
    secondary = 1 if "结束后" in event.event_time else 0
    return (primary, secondary, event.created_at.isoformat())


def _timeline_sort_key(event: TimelineEvent) -> tuple[int, int, int, str]:
    if event.position is not None:
        return (0, event.position, 0, "")
    primary, secondary, created = _timeline_heuristic_sort_key(event)
    return (1, primary, secondary, created)


async def find_timeline_event_by_key(
    session: AsyncSession,
    *,
    novel_id: UUID,
    title: str,
    event_time: str,
) -> TimelineEvent | None:
    target_key = _timeline_event_key(title, event_time)
    events = list(
        await session.scalars(select(TimelineEvent).where(TimelineEvent.novel_id == novel_id))
    )
    for event in events:
        if _timeline_event_key(event.title, event.event_time) == target_key:
            return event
    return None


def deduplicate_timeline_events(events: list[TimelineEvent]) -> list[TimelineEvent]:
    latest_by_key: dict[tuple[str, str], TimelineEvent] = {}
    for event in sorted(events, key=lambda item: item.created_at):
        latest_by_key[_timeline_event_key(event.title, event.event_time)] = event
    return list(latest_by_key.values())


def sort_timeline_events(events: list[TimelineEvent]) -> list[TimelineEvent]:
    return sorted(events, key=_timeline_sort_key)


def prepare_timeline_events(events: list[TimelineEvent]) -> list[TimelineEvent]:
    return sort_timeline_events(deduplicate_timeline_events(events))


def _character_state_snapshot(state: CharacterState) -> dict[str, Any]:
    return {
        "id": str(state.id),
        "character_name": state.character_name,
        "state": state.state,
        "scope": state.scope,
        "metadata": state.extra_metadata,
    }


def _character_attribute_snapshot(attribute: CharacterAttribute) -> dict[str, Any]:
    return {
        "id": str(attribute.id),
        "character_name": attribute.character_name,
        "attribute_key": attribute.attribute_key,
        "value": attribute.value,
        "unit": attribute.unit,
        "scope": attribute.scope,
        "metadata": attribute.extra_metadata,
    }


def _inventory_item_snapshot(item: InventoryItem) -> dict[str, Any]:
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


def _map_location_snapshot(location: MapLocation) -> dict[str, Any]:
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


def _normalize_character_state_name(character_name: str) -> str:
    return character_name.strip()


def _normalize_character_state_scope(scope: str) -> str:
    normalized = scope.strip()
    return normalized or "current"


def _normalize_story_label(value: str) -> str:
    return " ".join(value.split())


def _normalize_character_state_text(state: str) -> str:
    return " ".join(state.split())


def _character_state_key(character_name: str, scope: str) -> tuple[str, str]:
    return (_normalize_character_state_name(character_name), _normalize_character_state_scope(scope))


async def find_character_state_by_key(
    session: AsyncSession,
    *,
    novel_id: UUID,
    character_name: str,
    scope: str,
) -> CharacterState | None:
    target_name, target_scope = _character_state_key(character_name, scope)
    states = list(
        await session.scalars(select(CharacterState).where(CharacterState.novel_id == novel_id))
    )
    for state in states:
        if _character_state_key(state.character_name, state.scope) == (target_name, target_scope):
            return state
    return None


def deduplicate_character_states(states: list[CharacterState]) -> list[CharacterState]:
    latest_by_key: dict[tuple[str, str], CharacterState] = {}
    for state in sorted(states, key=lambda item: item.created_at):
        latest_by_key[_character_state_key(state.character_name, state.scope)] = state
    return sorted(
        latest_by_key.values(),
        key=lambda item: (_normalize_character_state_name(item.character_name), item.created_at),
    )


def _relationship_edge_snapshot(edge: RelationshipEdge) -> dict[str, Any]:
    return {
        "id": str(edge.id),
        "source_character": edge.source_character,
        "target_character": edge.target_character,
        "relationship_type": edge.relationship_type,
        "description": edge.description,
        "metadata": edge.extra_metadata,
    }


async def record_material_change(
    session: AsyncSession,
    *,
    novel_id: UUID,
    material_type: str,
    material_id: UUID,
    action: str,
    actor_source: MaterialActorSource,
    summary: str,
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
) -> MaterialChange:
    change = MaterialChange(
        novel_id=novel_id,
        material_type=material_type,
        material_id=material_id,
        action=action,
        actor_source=actor_source,
        summary=summary,
        before_data=before_data,
        after_data=after_data,
    )
    session.add(change)
    await session.flush()
    return change


async def list_material_changes(
    session: AsyncSession,
    *,
    novel_id: UUID,
    material_type: str | None = None,
    material_id: UUID | None = None,
    limit: int = 50,
) -> list[MaterialChange]:
    query = select(MaterialChange).where(MaterialChange.novel_id == novel_id)
    if material_type is not None:
        query = query.where(MaterialChange.material_type == material_type)
    if material_id is not None:
        query = query.where(MaterialChange.material_id == material_id)
    query = query.order_by(MaterialChange.created_at.desc(), MaterialChange.id.desc()).limit(limit)
    return list(await session.scalars(query))


async def _remove_rag_chunk(
    session: AsyncSession,
    *,
    novel_id: UUID,
    source_type: str,
    source_id: str,
) -> None:
    await session.execute(
        delete(RagChunk).where(
            RagChunk.novel_id == novel_id,
            RagChunk.source_type == source_type,
            RagChunk.source_id == source_id,
        )
    )


async def create_creative_asset(
    session: AsyncSession,
    *,
    novel_id: UUID,
    asset_type: str,
    name: str,
    summary: str,
    metadata: dict[str, Any] | None = None,
    actor_source: MaterialActorSource = "user",
) -> CreativeAsset:
    asset = CreativeAsset(
        novel_id=novel_id,
        asset_type=asset_type,
        name=name,
        summary=summary,
        extra_metadata=metadata or {},
    )
    session.add(asset)
    await session.flush()
    await index_text(
        session,
        novel_id=novel_id,
        source_type="creative_asset",
        source_id=str(asset.id),
        text=f"{asset.asset_type}: {asset.name}\n{asset.summary}",
        metadata={"asset_type": asset.asset_type},
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="creative_asset",
        material_id=asset.id,
        action="created",
        actor_source=actor_source,
        summary=f"创建创作资产「{asset.name}」",
        after_data=_creative_asset_snapshot(asset),
    )
    return asset


async def update_creative_asset(
    session: AsyncSession,
    *,
    novel_id: UUID,
    asset_id: UUID,
    asset_type: str | None = None,
    name: str | None = None,
    summary: str | None = None,
    metadata: dict[str, Any] | None = None,
    actor_source: MaterialActorSource = "user",
) -> CreativeAsset | None:
    asset = await session.scalar(
        select(CreativeAsset).where(CreativeAsset.id == asset_id, CreativeAsset.novel_id == novel_id)
    )
    if asset is None:
        return None

    before = _creative_asset_snapshot(asset)
    if asset_type is not None:
        asset.asset_type = asset_type
    if name is not None:
        asset.name = name
    if summary is not None:
        asset.summary = summary
    if metadata is not None:
        asset.extra_metadata = metadata

    await index_text(
        session,
        novel_id=novel_id,
        source_type="creative_asset",
        source_id=str(asset.id),
        text=f"{asset.asset_type}: {asset.name}\n{asset.summary}",
        metadata={"asset_type": asset.asset_type},
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="creative_asset",
        material_id=asset.id,
        action="updated",
        actor_source=actor_source,
        summary=f"更新创作资产「{asset.name}」",
        before_data=before,
        after_data=_creative_asset_snapshot(asset),
    )
    return asset


async def delete_creative_asset(
    session: AsyncSession,
    *,
    novel_id: UUID,
    asset_id: UUID,
    actor_source: MaterialActorSource = "user",
) -> bool:
    asset = await session.scalar(
        select(CreativeAsset).where(CreativeAsset.id == asset_id, CreativeAsset.novel_id == novel_id)
    )
    if asset is None:
        return False

    before = _creative_asset_snapshot(asset)
    await _remove_rag_chunk(
        session,
        novel_id=novel_id,
        source_type="creative_asset",
        source_id=str(asset.id),
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="creative_asset",
        material_id=asset.id,
        action="deleted",
        actor_source=actor_source,
        summary=f"删除创作资产「{asset.name}」",
        before_data=before,
    )
    await session.delete(asset)
    return True


async def delete_creative_assets(
    session: AsyncSession,
    *,
    novel_id: UUID,
    asset_ids: list[UUID],
    actor_source: MaterialActorSource = "user",
) -> dict[str, list[str]]:
    deleted: list[str] = []
    missing: list[str] = []
    for asset_id in asset_ids:
        if await delete_creative_asset(
            session,
            novel_id=novel_id,
            asset_id=asset_id,
            actor_source=actor_source,
        ):
            deleted.append(str(asset_id))
        else:
            missing.append(str(asset_id))
    return {"deleted": deleted, "missing": missing}


async def create_timeline_event(
    session: AsyncSession,
    *,
    novel_id: UUID,
    title: str,
    event_time: str,
    summary: str,
    position: int | None = None,
    metadata: dict[str, Any] | None = None,
    actor_source: MaterialActorSource = "user",
) -> TimelineEvent:
    normalized_title = _normalize_timeline_label(title)
    normalized_event_time = _normalize_timeline_label(event_time)
    normalized_summary = summary.strip()
    existing = await find_timeline_event_by_key(
        session,
        novel_id=novel_id,
        title=normalized_title,
        event_time=normalized_event_time,
    )
    if existing is not None:
        if _normalize_timeline_summary(existing.summary) == _normalize_timeline_summary(normalized_summary):
            return existing
        updated = await update_timeline_event(
            session,
            novel_id=novel_id,
            event_id=existing.id,
            title=normalized_title,
            event_time=normalized_event_time,
            summary=normalized_summary,
            position=position,
            metadata=metadata,
            actor_source=actor_source,
        )
        return updated or existing

    event = TimelineEvent(
        novel_id=novel_id,
        title=normalized_title,
        event_time=normalized_event_time,
        summary=normalized_summary,
        position=position,
        extra_metadata=metadata or {},
    )
    session.add(event)
    await session.flush()
    await index_text(
        session,
        novel_id=novel_id,
        source_type="timeline_event",
        source_id=str(event.id),
        text=f"{event.event_time}: {event.title}\n{event.summary}",
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="timeline_event",
        material_id=event.id,
        action="created",
        actor_source=actor_source,
        summary=f"创建时间线事件「{event.title}」",
        after_data=_timeline_event_snapshot(event),
    )
    return event


async def update_timeline_event(
    session: AsyncSession,
    *,
    novel_id: UUID,
    event_id: UUID,
    title: str | None = None,
    event_time: str | None = None,
    summary: str | None = None,
    position: int | None = None,
    metadata: dict[str, Any] | None = None,
    actor_source: MaterialActorSource = "user",
) -> TimelineEvent | None:
    event = await session.scalar(
        select(TimelineEvent).where(TimelineEvent.id == event_id, TimelineEvent.novel_id == novel_id)
    )
    if event is None:
        return None

    before = _timeline_event_snapshot(event)
    if title is not None:
        event.title = title
    if event_time is not None:
        event.event_time = event_time
    if summary is not None:
        event.summary = summary
    if position is not None:
        event.position = position
    if metadata is not None:
        event.extra_metadata = metadata

    await index_text(
        session,
        novel_id=novel_id,
        source_type="timeline_event",
        source_id=str(event.id),
        text=f"{event.event_time}: {event.title}\n{event.summary}",
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="timeline_event",
        material_id=event.id,
        action="updated",
        actor_source=actor_source,
        summary=f"更新时间线事件「{event.title}」",
        before_data=before,
        after_data=_timeline_event_snapshot(event),
    )
    return event


async def reorder_timeline_events(
    session: AsyncSession,
    *,
    novel_id: UUID,
    event_ids: list[UUID],
    actor_source: MaterialActorSource = "user",
) -> list[TimelineEvent] | None:
    events = list(
        await session.scalars(select(TimelineEvent).where(TimelineEvent.novel_id == novel_id))
    )
    event_by_id = {event.id: event for event in events}

    ordered: list[TimelineEvent] = []
    seen: set[UUID] = set()
    for event_id in event_ids:
        event = event_by_id.get(event_id)
        if event is None:
            return None
        if event_id in seen:
            continue
        seen.add(event_id)
        ordered.append(event)

    remaining = sort_timeline_events([event for event in events if event.id not in seen])
    full_order = ordered + remaining
    if not full_order:
        return []

    for index, event in enumerate(full_order, start=1):
        event.position = index

    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="timeline_event",
        material_id=full_order[0].id,
        action="updated",
        actor_source=actor_source,
        summary="调整时间线排序",
        after_data={"event_ids": [str(event.id) for event in full_order]},
    )
    return full_order


async def delete_timeline_event(
    session: AsyncSession,
    *,
    novel_id: UUID,
    event_id: UUID,
    actor_source: MaterialActorSource = "user",
) -> bool:
    event = await session.scalar(
        select(TimelineEvent).where(TimelineEvent.id == event_id, TimelineEvent.novel_id == novel_id)
    )
    if event is None:
        return False

    before = _timeline_event_snapshot(event)
    await _remove_rag_chunk(
        session,
        novel_id=novel_id,
        source_type="timeline_event",
        source_id=str(event.id),
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="timeline_event",
        material_id=event.id,
        action="deleted",
        actor_source=actor_source,
        summary=f"删除时间线事件「{event.title}」",
        before_data=before,
    )
    await session.delete(event)
    return True


async def create_character_state(
    session: AsyncSession,
    *,
    novel_id: UUID,
    character_name: str,
    state: str,
    scope: str = "global",
    metadata: dict[str, Any] | None = None,
    actor_source: MaterialActorSource = "user",
) -> CharacterState:
    normalized_name = _normalize_character_state_name(character_name)
    normalized_scope = _normalize_character_state_scope(scope)
    normalized_state = state.strip()
    existing = await find_character_state_by_key(
        session,
        novel_id=novel_id,
        character_name=normalized_name,
        scope=normalized_scope,
    )
    if existing is not None:
        if _normalize_character_state_text(existing.state) == _normalize_character_state_text(normalized_state):
            return existing
        updated = await update_character_state_record(
            session,
            novel_id=novel_id,
            state_id=existing.id,
            character_name=normalized_name,
            state=normalized_state,
            scope=normalized_scope,
            metadata=metadata,
            actor_source=actor_source,
        )
        return updated or existing

    character_state = CharacterState(
        novel_id=novel_id,
        character_name=normalized_name,
        state=normalized_state,
        scope=normalized_scope,
        extra_metadata=metadata or {},
    )
    session.add(character_state)
    await session.flush()
    await index_text(
        session,
        novel_id=novel_id,
        source_type="character_state",
        source_id=str(character_state.id),
        text=f"{character_state.character_name} [{character_state.scope}]: {character_state.state}",
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="character_state",
        material_id=character_state.id,
        action="created",
        actor_source=actor_source,
        summary=f"记录角色「{character_state.character_name}」状态",
        after_data=_character_state_snapshot(character_state),
    )
    return character_state


async def update_character_state_record(
    session: AsyncSession,
    *,
    novel_id: UUID,
    state_id: UUID,
    character_name: str | None = None,
    state: str | None = None,
    scope: str | None = None,
    metadata: dict[str, Any] | None = None,
    actor_source: MaterialActorSource = "user",
) -> CharacterState | None:
    character_state = await session.scalar(
        select(CharacterState).where(CharacterState.id == state_id, CharacterState.novel_id == novel_id)
    )
    if character_state is None:
        return None

    before = _character_state_snapshot(character_state)
    if character_name is not None:
        character_state.character_name = character_name
    if state is not None:
        character_state.state = state
    if scope is not None:
        character_state.scope = scope
    if metadata is not None:
        character_state.extra_metadata = metadata

    await index_text(
        session,
        novel_id=novel_id,
        source_type="character_state",
        source_id=str(character_state.id),
        text=f"{character_state.character_name} [{character_state.scope}]: {character_state.state}",
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="character_state",
        material_id=character_state.id,
        action="updated",
        actor_source=actor_source,
        summary=f"更新角色「{character_state.character_name}」状态",
        before_data=before,
        after_data=_character_state_snapshot(character_state),
    )
    return character_state


async def delete_character_state(
    session: AsyncSession,
    *,
    novel_id: UUID,
    state_id: UUID,
    actor_source: MaterialActorSource = "user",
) -> bool:
    character_state = await session.scalar(
        select(CharacterState).where(CharacterState.id == state_id, CharacterState.novel_id == novel_id)
    )
    if character_state is None:
        return False

    before = _character_state_snapshot(character_state)
    await _remove_rag_chunk(
        session,
        novel_id=novel_id,
        source_type="character_state",
        source_id=str(character_state.id),
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="character_state",
        material_id=character_state.id,
        action="deleted",
        actor_source=actor_source,
        summary=f"删除角色「{character_state.character_name}」状态记录",
        before_data=before,
    )
    await session.delete(character_state)
    return True


async def find_character_attribute_by_key(
    session: AsyncSession,
    *,
    novel_id: UUID,
    character_name: str,
    attribute_key: str,
    scope: str,
) -> CharacterAttribute | None:
    return await session.scalar(
        select(CharacterAttribute).where(
            CharacterAttribute.novel_id == novel_id,
            CharacterAttribute.character_name == _normalize_story_label(character_name),
            CharacterAttribute.attribute_key == _normalize_story_label(attribute_key),
            CharacterAttribute.scope == _normalize_story_label(scope),
        )
    )


async def list_character_attributes(
    session: AsyncSession,
    *,
    novel_id: UUID,
    character_name: str | None = None,
    scope: str | None = None,
) -> list[CharacterAttribute]:
    query = select(CharacterAttribute).where(CharacterAttribute.novel_id == novel_id)
    if character_name is not None:
        query = query.where(CharacterAttribute.character_name == _normalize_story_label(character_name))
    if scope is not None:
        query = query.where(CharacterAttribute.scope == _normalize_story_label(scope))
    query = query.order_by(CharacterAttribute.character_name, CharacterAttribute.attribute_key, CharacterAttribute.created_at)
    return list(await session.scalars(query))


async def upsert_character_attribute(
    session: AsyncSession,
    *,
    novel_id: UUID,
    character_name: str,
    attribute_key: str,
    value: Any,
    unit: str = "",
    scope: str = "current",
    metadata: dict[str, Any] | None = None,
    actor_source: MaterialActorSource = "user",
) -> CharacterAttribute:
    normalized_name = _normalize_story_label(character_name)
    normalized_key = _normalize_story_label(attribute_key)
    normalized_scope = _normalize_story_label(scope) or "current"
    existing = await find_character_attribute_by_key(
        session,
        novel_id=novel_id,
        character_name=normalized_name,
        attribute_key=normalized_key,
        scope=normalized_scope,
    )
    if existing is not None:
        updated = await update_character_attribute(
            session,
            novel_id=novel_id,
            attribute_id=existing.id,
            value=value,
            unit=unit,
            metadata=metadata,
            actor_source=actor_source,
        )
        return updated or existing

    attribute = CharacterAttribute(
        novel_id=novel_id,
        character_name=normalized_name,
        attribute_key=normalized_key,
        value=value,
        unit=unit,
        scope=normalized_scope,
        extra_metadata=metadata or {},
    )
    session.add(attribute)
    await session.flush()
    await index_text(
        session,
        novel_id=novel_id,
        source_type="character_attribute",
        source_id=str(attribute.id),
        text=f"{attribute.character_name} [{attribute.scope}] {attribute.attribute_key} = {attribute.value} {attribute.unit}".strip(),
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="character_attribute",
        material_id=attribute.id,
        action="created",
        actor_source=actor_source,
        summary=f"记录角色「{attribute.character_name}」属性 {attribute.attribute_key}",
        after_data=_character_attribute_snapshot(attribute),
    )
    return attribute


async def update_character_attribute(
    session: AsyncSession,
    *,
    novel_id: UUID,
    attribute_id: UUID,
    character_name: str | None = None,
    attribute_key: str | None = None,
    value: Any | None = None,
    unit: str | None = None,
    scope: str | None = None,
    metadata: dict[str, Any] | None = None,
    actor_source: MaterialActorSource = "user",
) -> CharacterAttribute | None:
    attribute = await session.scalar(
        select(CharacterAttribute).where(CharacterAttribute.id == attribute_id, CharacterAttribute.novel_id == novel_id)
    )
    if attribute is None:
        return None

    before = _character_attribute_snapshot(attribute)
    if character_name is not None:
        attribute.character_name = _normalize_story_label(character_name)
    if attribute_key is not None:
        attribute.attribute_key = _normalize_story_label(attribute_key)
    if value is not None:
        attribute.value = value
    if unit is not None:
        attribute.unit = unit
    if scope is not None:
        attribute.scope = _normalize_story_label(scope) or "current"
    if metadata is not None:
        attribute.extra_metadata = metadata

    await index_text(
        session,
        novel_id=novel_id,
        source_type="character_attribute",
        source_id=str(attribute.id),
        text=f"{attribute.character_name} [{attribute.scope}] {attribute.attribute_key} = {attribute.value} {attribute.unit}".strip(),
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="character_attribute",
        material_id=attribute.id,
        action="updated",
        actor_source=actor_source,
        summary=f"更新角色「{attribute.character_name}」属性 {attribute.attribute_key}",
        before_data=before,
        after_data=_character_attribute_snapshot(attribute),
    )
    return attribute


async def delete_character_attribute(
    session: AsyncSession,
    *,
    novel_id: UUID,
    attribute_id: UUID,
    actor_source: MaterialActorSource = "user",
) -> bool:
    attribute = await session.scalar(
        select(CharacterAttribute).where(CharacterAttribute.id == attribute_id, CharacterAttribute.novel_id == novel_id)
    )
    if attribute is None:
        return False

    before = _character_attribute_snapshot(attribute)
    await _remove_rag_chunk(
        session,
        novel_id=novel_id,
        source_type="character_attribute",
        source_id=str(attribute.id),
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="character_attribute",
        material_id=attribute.id,
        action="deleted",
        actor_source=actor_source,
        summary=f"删除角色「{attribute.character_name}」属性 {attribute.attribute_key}",
        before_data=before,
    )
    await session.delete(attribute)
    return True


async def find_inventory_item_by_key(
    session: AsyncSession,
    *,
    novel_id: UUID,
    owner_name: str,
    item_name: str,
    location_name: str | None,
) -> InventoryItem | None:
    normalized_location = _normalize_story_label(location_name) if location_name else None
    return await session.scalar(
        select(InventoryItem).where(
            InventoryItem.novel_id == novel_id,
            InventoryItem.owner_name == _normalize_story_label(owner_name),
            InventoryItem.item_name == _normalize_story_label(item_name),
            InventoryItem.location_name == normalized_location,
        )
    )


async def list_inventory_items(
    session: AsyncSession,
    *,
    novel_id: UUID,
    owner_name: str | None = None,
    location_name: str | None = None,
) -> list[InventoryItem]:
    query = select(InventoryItem).where(InventoryItem.novel_id == novel_id)
    if owner_name is not None:
        query = query.where(InventoryItem.owner_name == _normalize_story_label(owner_name))
    if location_name is not None:
        query = query.where(InventoryItem.location_name == _normalize_story_label(location_name))
    query = query.order_by(InventoryItem.owner_name, InventoryItem.item_name, InventoryItem.created_at)
    return list(await session.scalars(query))


async def upsert_inventory_item(
    session: AsyncSession,
    *,
    novel_id: UUID,
    owner_name: str,
    item_name: str,
    quantity: float,
    unit: str = "",
    location_name: str | None = None,
    description: str = "",
    metadata: dict[str, Any] | None = None,
    actor_source: MaterialActorSource = "user",
) -> InventoryItem:
    normalized_owner = _normalize_story_label(owner_name)
    normalized_item = _normalize_story_label(item_name)
    normalized_location = _normalize_story_label(location_name) if location_name else None
    existing = await find_inventory_item_by_key(
        session,
        novel_id=novel_id,
        owner_name=normalized_owner,
        item_name=normalized_item,
        location_name=normalized_location,
    )
    if existing is not None:
        updated = await update_inventory_item(
            session,
            novel_id=novel_id,
            item_id=existing.id,
            quantity=quantity,
            unit=unit,
            description=description,
            metadata=metadata,
            actor_source=actor_source,
        )
        return updated or existing

    item = InventoryItem(
        novel_id=novel_id,
        owner_name=normalized_owner,
        item_name=normalized_item,
        quantity=quantity,
        unit=unit,
        location_name=normalized_location,
        description=description,
        extra_metadata=metadata or {},
    )
    session.add(item)
    await session.flush()
    await index_text(
        session,
        novel_id=novel_id,
        source_type="inventory_item",
        source_id=str(item.id),
        text=f"{item.owner_name} 持有 {item.quantity:g}{item.unit} {item.item_name} @ {item.location_name or '未知位置'}\n{item.description}",
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="inventory_item",
        material_id=item.id,
        action="created",
        actor_source=actor_source,
        summary=f"记录「{item.owner_name}」背包物品「{item.item_name}」",
        after_data=_inventory_item_snapshot(item),
    )
    return item


async def update_inventory_item(
    session: AsyncSession,
    *,
    novel_id: UUID,
    item_id: UUID,
    owner_name: str | None = None,
    item_name: str | None = None,
    quantity: float | None = None,
    unit: str | None = None,
    location_name: str | None = None,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
    actor_source: MaterialActorSource = "user",
) -> InventoryItem | None:
    item = await session.scalar(
        select(InventoryItem).where(InventoryItem.id == item_id, InventoryItem.novel_id == novel_id)
    )
    if item is None:
        return None

    before = _inventory_item_snapshot(item)
    if owner_name is not None:
        item.owner_name = _normalize_story_label(owner_name)
    if item_name is not None:
        item.item_name = _normalize_story_label(item_name)
    if quantity is not None:
        item.quantity = quantity
    if unit is not None:
        item.unit = unit
    if location_name is not None:
        item.location_name = _normalize_story_label(location_name)
    if description is not None:
        item.description = description
    if metadata is not None:
        item.extra_metadata = metadata

    await index_text(
        session,
        novel_id=novel_id,
        source_type="inventory_item",
        source_id=str(item.id),
        text=f"{item.owner_name} 持有 {item.quantity:g}{item.unit} {item.item_name} @ {item.location_name or '未知位置'}\n{item.description}",
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="inventory_item",
        material_id=item.id,
        action="updated",
        actor_source=actor_source,
        summary=f"更新「{item.owner_name}」背包物品「{item.item_name}」",
        before_data=before,
        after_data=_inventory_item_snapshot(item),
    )
    return item


async def delete_inventory_item(
    session: AsyncSession,
    *,
    novel_id: UUID,
    item_id: UUID,
    actor_source: MaterialActorSource = "user",
) -> bool:
    item = await session.scalar(
        select(InventoryItem).where(InventoryItem.id == item_id, InventoryItem.novel_id == novel_id)
    )
    if item is None:
        return False

    before = _inventory_item_snapshot(item)
    await _remove_rag_chunk(
        session,
        novel_id=novel_id,
        source_type="inventory_item",
        source_id=str(item.id),
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="inventory_item",
        material_id=item.id,
        action="deleted",
        actor_source=actor_source,
        summary=f"删除「{item.owner_name}」背包物品「{item.item_name}」",
        before_data=before,
    )
    await session.delete(item)
    return True


async def find_map_location_by_name(
    session: AsyncSession,
    *,
    novel_id: UUID,
    name: str,
) -> MapLocation | None:
    return await session.scalar(
        select(MapLocation).where(
            MapLocation.novel_id == novel_id,
            MapLocation.name == _normalize_story_label(name),
        )
    )


async def list_map_locations(
    session: AsyncSession,
    *,
    novel_id: UUID,
    location_type: str | None = None,
    parent_name: str | None = None,
) -> list[MapLocation]:
    query = select(MapLocation).where(MapLocation.novel_id == novel_id)
    if location_type is not None:
        query = query.where(MapLocation.location_type == _normalize_story_label(location_type))
    if parent_name is not None:
        query = query.where(MapLocation.parent_name == _normalize_story_label(parent_name))
    query = query.order_by(MapLocation.parent_name, MapLocation.name, MapLocation.created_at)
    return list(await session.scalars(query))


async def upsert_map_location(
    session: AsyncSession,
    *,
    novel_id: UUID,
    name: str,
    location_type: str = "location",
    summary: str = "",
    parent_name: str | None = None,
    coordinates: dict[str, Any] | None = None,
    adjacent_location_names: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    actor_source: MaterialActorSource = "user",
) -> MapLocation:
    normalized_name = _normalize_story_label(name)
    existing = await find_map_location_by_name(session, novel_id=novel_id, name=normalized_name)
    if existing is not None:
        updated = await update_map_location(
            session,
            novel_id=novel_id,
            location_id=existing.id,
            location_type=location_type,
            summary=summary,
            parent_name=parent_name,
            coordinates=coordinates,
            adjacent_location_names=adjacent_location_names,
            metadata=metadata,
            actor_source=actor_source,
        )
        return updated or existing

    location = MapLocation(
        novel_id=novel_id,
        name=normalized_name,
        location_type=_normalize_story_label(location_type) or "location",
        summary=summary,
        parent_name=_normalize_story_label(parent_name) if parent_name else None,
        coordinates=coordinates or {},
        adjacent_location_names=adjacent_location_names or [],
        extra_metadata=metadata or {},
    )
    session.add(location)
    await session.flush()
    await index_text(
        session,
        novel_id=novel_id,
        source_type="map_location",
        source_id=str(location.id),
        text=f"{location.location_type}: {location.name}\n{location.summary}\n相邻: {', '.join(location.adjacent_location_names)}",
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="map_location",
        material_id=location.id,
        action="created",
        actor_source=actor_source,
        summary=f"记录地图地点「{location.name}」",
        after_data=_map_location_snapshot(location),
    )
    return location


async def update_map_location(
    session: AsyncSession,
    *,
    novel_id: UUID,
    location_id: UUID,
    name: str | None = None,
    location_type: str | None = None,
    summary: str | None = None,
    parent_name: str | None = None,
    coordinates: dict[str, Any] | None = None,
    adjacent_location_names: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    actor_source: MaterialActorSource = "user",
) -> MapLocation | None:
    location = await session.scalar(
        select(MapLocation).where(MapLocation.id == location_id, MapLocation.novel_id == novel_id)
    )
    if location is None:
        return None

    before = _map_location_snapshot(location)
    if name is not None:
        location.name = _normalize_story_label(name)
    if location_type is not None:
        location.location_type = _normalize_story_label(location_type) or "location"
    if summary is not None:
        location.summary = summary
    if parent_name is not None:
        location.parent_name = _normalize_story_label(parent_name)
    if coordinates is not None:
        location.coordinates = coordinates
    if adjacent_location_names is not None:
        location.adjacent_location_names = adjacent_location_names
    if metadata is not None:
        location.extra_metadata = metadata

    await index_text(
        session,
        novel_id=novel_id,
        source_type="map_location",
        source_id=str(location.id),
        text=f"{location.location_type}: {location.name}\n{location.summary}\n相邻: {', '.join(location.adjacent_location_names)}",
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="map_location",
        material_id=location.id,
        action="updated",
        actor_source=actor_source,
        summary=f"更新地图地点「{location.name}」",
        before_data=before,
        after_data=_map_location_snapshot(location),
    )
    return location


async def delete_map_location(
    session: AsyncSession,
    *,
    novel_id: UUID,
    location_id: UUID,
    actor_source: MaterialActorSource = "user",
) -> bool:
    location = await session.scalar(
        select(MapLocation).where(MapLocation.id == location_id, MapLocation.novel_id == novel_id)
    )
    if location is None:
        return False

    before = _map_location_snapshot(location)
    await _remove_rag_chunk(
        session,
        novel_id=novel_id,
        source_type="map_location",
        source_id=str(location.id),
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="map_location",
        material_id=location.id,
        action="deleted",
        actor_source=actor_source,
        summary=f"删除地图地点「{location.name}」",
        before_data=before,
    )
    await session.delete(location)
    return True


async def create_relationship_edge(
    session: AsyncSession,
    *,
    novel_id: UUID,
    source_character: str,
    target_character: str,
    relationship_type: str,
    description: str,
    metadata: dict[str, Any] | None = None,
    actor_source: MaterialActorSource = "user",
) -> RelationshipEdge:
    existing = await session.scalar(
        select(RelationshipEdge).where(
            RelationshipEdge.novel_id == novel_id,
            RelationshipEdge.source_character == source_character,
            RelationshipEdge.target_character == target_character,
            RelationshipEdge.relationship_type == relationship_type,
        )
    )
    if existing is not None:
        if description.strip() and description != existing.description:
            updated = await update_relationship_edge(
                session,
                novel_id=novel_id,
                edge_id=existing.id,
                description=description,
                metadata=metadata,
                actor_source=actor_source,
            )
            return updated or existing
        return existing

    edge = RelationshipEdge(
        novel_id=novel_id,
        source_character=source_character,
        target_character=target_character,
        relationship_type=relationship_type,
        description=description,
        extra_metadata=metadata or {},
    )
    session.add(edge)
    await session.flush()
    await index_text(
        session,
        novel_id=novel_id,
        source_type="relationship_edge",
        source_id=str(edge.id),
        text=f"{edge.source_character} {edge.relationship_type} {edge.target_character}: {edge.description}",
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="relationship_edge",
        material_id=edge.id,
        action="created",
        actor_source=actor_source,
        summary=f"记录 {edge.source_character} 与 {edge.target_character} 的关系",
        after_data=_relationship_edge_snapshot(edge),
    )
    return edge


async def update_relationship_edge(
    session: AsyncSession,
    *,
    novel_id: UUID,
    edge_id: UUID,
    source_character: str | None = None,
    target_character: str | None = None,
    relationship_type: str | None = None,
    description: str | None = None,
    metadata: dict[str, Any] | None = None,
    actor_source: MaterialActorSource = "user",
) -> RelationshipEdge | None:
    edge = await session.scalar(
        select(RelationshipEdge).where(RelationshipEdge.id == edge_id, RelationshipEdge.novel_id == novel_id)
    )
    if edge is None:
        return None

    before = _relationship_edge_snapshot(edge)
    if source_character is not None:
        edge.source_character = source_character
    if target_character is not None:
        edge.target_character = target_character
    if relationship_type is not None:
        edge.relationship_type = relationship_type
    if description is not None:
        edge.description = description
    if metadata is not None:
        edge.extra_metadata = metadata

    await index_text(
        session,
        novel_id=novel_id,
        source_type="relationship_edge",
        source_id=str(edge.id),
        text=f"{edge.source_character} {edge.relationship_type} {edge.target_character}: {edge.description}",
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="relationship_edge",
        material_id=edge.id,
        action="updated",
        actor_source=actor_source,
        summary=f"更新 {edge.source_character} 与 {edge.target_character} 的关系",
        before_data=before,
        after_data=_relationship_edge_snapshot(edge),
    )
    return edge


async def delete_relationship_edge(
    session: AsyncSession,
    *,
    novel_id: UUID,
    edge_id: UUID,
    actor_source: MaterialActorSource = "user",
) -> bool:
    edge = await session.scalar(
        select(RelationshipEdge).where(RelationshipEdge.id == edge_id, RelationshipEdge.novel_id == novel_id)
    )
    if edge is None:
        return False

    before = _relationship_edge_snapshot(edge)
    await _remove_rag_chunk(
        session,
        novel_id=novel_id,
        source_type="relationship_edge",
        source_id=str(edge.id),
    )
    await record_material_change(
        session,
        novel_id=novel_id,
        material_type="relationship_edge",
        material_id=edge.id,
        action="deleted",
        actor_source=actor_source,
        summary=f"删除 {edge.source_character} 与 {edge.target_character} 的关系",
        before_data=before,
    )
    await session.delete(edge)
    return True
