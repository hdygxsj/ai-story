from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CharacterState,
    CreativeAsset,
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
        "metadata": event.extra_metadata,
    }


def _character_state_snapshot(state: CharacterState) -> dict[str, Any]:
    return {
        "id": str(state.id),
        "character_name": state.character_name,
        "state": state.state,
        "scope": state.scope,
        "metadata": state.extra_metadata,
    }


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


async def create_timeline_event(
    session: AsyncSession,
    *,
    novel_id: UUID,
    title: str,
    event_time: str,
    summary: str,
    metadata: dict[str, Any] | None = None,
    actor_source: MaterialActorSource = "user",
) -> TimelineEvent:
    event = TimelineEvent(
        novel_id=novel_id,
        title=title,
        event_time=event_time,
        summary=summary,
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
    character_state = CharacterState(
        novel_id=novel_id,
        character_name=character_name,
        state=state,
        scope=scope,
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
