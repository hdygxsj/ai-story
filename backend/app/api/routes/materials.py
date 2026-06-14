from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import CharacterState, CreativeAsset, RelationshipEdge, TimelineEvent, User
from app.schemas.materials import (
    CharacterStateCreate,
    CharacterStateResponse,
    CharacterStateUpdate,
    CreativeAssetCreate,
    CreativeAssetResponse,
    CreativeAssetUpdate,
    MaterialChangeResponse,
    RelationshipEdgeCreate,
    RelationshipEdgeResponse,
    RelationshipEdgeUpdate,
    TimelineEventCreate,
    TimelineEventResponse,
    TimelineEventUpdate,
)
from app.services.materials import (
    create_character_state,
    create_creative_asset,
    create_relationship_edge,
    create_timeline_event,
    deduplicate_character_states,
    delete_character_state,
    delete_creative_asset,
    delete_relationship_edge,
    delete_timeline_event,
    list_material_changes,
    prepare_timeline_events,
    update_character_state_record,
    update_creative_asset,
    update_relationship_edge,
    update_timeline_event,
)
from app.services.novels import get_owned_novel

router = APIRouter(tags=["materials"])


@router.post("/novels/{novel_id}/creative-assets", response_model=CreativeAssetResponse, status_code=status.HTTP_201_CREATED)
async def create_creative_asset_route(
    novel_id: UUID,
    payload: CreativeAssetCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CreativeAsset:
    await get_owned_novel(session, current_user, novel_id)
    asset = await create_creative_asset(
        session,
        novel_id=novel_id,
        asset_type=payload.asset_type,
        name=payload.name,
        summary=payload.summary,
        metadata=payload.metadata,
        actor_source="user",
    )
    await session.commit()
    await session.refresh(asset)
    return asset


@router.get("/novels/{novel_id}/creative-assets", response_model=list[CreativeAssetResponse])
async def list_creative_assets(
    novel_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[CreativeAsset]:
    await get_owned_novel(session, current_user, novel_id)
    return list(await session.scalars(select(CreativeAsset).where(CreativeAsset.novel_id == novel_id)))


@router.patch("/novels/{novel_id}/creative-assets/{asset_id}", response_model=CreativeAssetResponse)
async def update_creative_asset_route(
    novel_id: UUID,
    asset_id: UUID,
    payload: CreativeAssetUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CreativeAsset:
    await get_owned_novel(session, current_user, novel_id)
    asset = await update_creative_asset(
        session,
        novel_id=novel_id,
        asset_id=asset_id,
        asset_type=payload.asset_type,
        name=payload.name,
        summary=payload.summary,
        metadata=payload.metadata,
        actor_source="user",
    )
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="创作资产不存在。")
    await session.commit()
    await session.refresh(asset)
    return asset


@router.delete("/novels/{novel_id}/creative-assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_creative_asset_route(
    novel_id: UUID,
    asset_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await get_owned_novel(session, current_user, novel_id)
    deleted = await delete_creative_asset(
        session,
        novel_id=novel_id,
        asset_id=asset_id,
        actor_source="user",
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="创作资产不存在。")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/novels/{novel_id}/timeline-events", response_model=TimelineEventResponse, status_code=status.HTTP_201_CREATED)
async def create_timeline_event_route(
    novel_id: UUID,
    payload: TimelineEventCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TimelineEvent:
    await get_owned_novel(session, current_user, novel_id)
    event = await create_timeline_event(
        session,
        novel_id=novel_id,
        title=payload.title,
        event_time=payload.event_time,
        summary=payload.summary,
        metadata=payload.metadata,
        actor_source="user",
    )
    await session.commit()
    await session.refresh(event)
    return event


@router.get("/novels/{novel_id}/timeline-events", response_model=list[TimelineEventResponse])
async def list_timeline_events(
    novel_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[TimelineEvent]:
    await get_owned_novel(session, current_user, novel_id)
    events = list(await session.scalars(select(TimelineEvent).where(TimelineEvent.novel_id == novel_id)))
    return prepare_timeline_events(events)


@router.patch("/novels/{novel_id}/timeline-events/{event_id}", response_model=TimelineEventResponse)
async def update_timeline_event_route(
    novel_id: UUID,
    event_id: UUID,
    payload: TimelineEventUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TimelineEvent:
    await get_owned_novel(session, current_user, novel_id)
    event = await update_timeline_event(
        session,
        novel_id=novel_id,
        event_id=event_id,
        title=payload.title,
        event_time=payload.event_time,
        summary=payload.summary,
        metadata=payload.metadata,
        actor_source="user",
    )
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="时间线事件不存在。")
    await session.commit()
    await session.refresh(event)
    return event


@router.delete("/novels/{novel_id}/timeline-events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timeline_event_route(
    novel_id: UUID,
    event_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await get_owned_novel(session, current_user, novel_id)
    deleted = await delete_timeline_event(
        session,
        novel_id=novel_id,
        event_id=event_id,
        actor_source="user",
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="时间线事件不存在。")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/novels/{novel_id}/character-states", response_model=CharacterStateResponse, status_code=status.HTTP_201_CREATED)
async def create_character_state_route(
    novel_id: UUID,
    payload: CharacterStateCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CharacterState:
    await get_owned_novel(session, current_user, novel_id)
    state = await create_character_state(
        session,
        novel_id=novel_id,
        character_name=payload.character_name,
        state=payload.state,
        scope=payload.scope,
        metadata=payload.metadata,
        actor_source="user",
    )
    await session.commit()
    await session.refresh(state)
    return state


@router.get("/novels/{novel_id}/character-states", response_model=list[CharacterStateResponse])
async def list_character_states(
    novel_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[CharacterState]:
    await get_owned_novel(session, current_user, novel_id)
    states = list(await session.scalars(select(CharacterState).where(CharacterState.novel_id == novel_id)))
    return deduplicate_character_states(states)


@router.patch("/novels/{novel_id}/character-states/{state_id}", response_model=CharacterStateResponse)
async def update_character_state_route(
    novel_id: UUID,
    state_id: UUID,
    payload: CharacterStateUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CharacterState:
    await get_owned_novel(session, current_user, novel_id)
    state = await update_character_state_record(
        session,
        novel_id=novel_id,
        state_id=state_id,
        character_name=payload.character_name,
        state=payload.state,
        scope=payload.scope,
        metadata=payload.metadata,
        actor_source="user",
    )
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色状态不存在。")
    await session.commit()
    await session.refresh(state)
    return state


@router.delete("/novels/{novel_id}/character-states/{state_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character_state_route(
    novel_id: UUID,
    state_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await get_owned_novel(session, current_user, novel_id)
    deleted = await delete_character_state(
        session,
        novel_id=novel_id,
        state_id=state_id,
        actor_source="user",
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色状态不存在。")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/novels/{novel_id}/relationship-edges", response_model=RelationshipEdgeResponse, status_code=status.HTTP_201_CREATED)
async def create_relationship_edge_route(
    novel_id: UUID,
    payload: RelationshipEdgeCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RelationshipEdge:
    await get_owned_novel(session, current_user, novel_id)
    edge = await create_relationship_edge(
        session,
        novel_id=novel_id,
        source_character=payload.source_character,
        target_character=payload.target_character,
        relationship_type=payload.relationship_type,
        description=payload.description,
        metadata=payload.metadata,
        actor_source="user",
    )
    await session.commit()
    await session.refresh(edge)
    return edge


@router.get("/novels/{novel_id}/relationship-edges", response_model=list[RelationshipEdgeResponse])
async def list_relationship_edges(
    novel_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[RelationshipEdge]:
    await get_owned_novel(session, current_user, novel_id)
    return list(await session.scalars(select(RelationshipEdge).where(RelationshipEdge.novel_id == novel_id)))


@router.patch("/novels/{novel_id}/relationship-edges/{edge_id}", response_model=RelationshipEdgeResponse)
async def update_relationship_edge_route(
    novel_id: UUID,
    edge_id: UUID,
    payload: RelationshipEdgeUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RelationshipEdge:
    await get_owned_novel(session, current_user, novel_id)
    edge = await update_relationship_edge(
        session,
        novel_id=novel_id,
        edge_id=edge_id,
        source_character=payload.source_character,
        target_character=payload.target_character,
        relationship_type=payload.relationship_type,
        description=payload.description,
        metadata=payload.metadata,
        actor_source="user",
    )
    if edge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="人物关系不存在。")
    await session.commit()
    await session.refresh(edge)
    return edge


@router.delete("/novels/{novel_id}/relationship-edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_relationship_edge_route(
    novel_id: UUID,
    edge_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await get_owned_novel(session, current_user, novel_id)
    deleted = await delete_relationship_edge(
        session,
        novel_id=novel_id,
        edge_id=edge_id,
        actor_source="user",
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="人物关系不存在。")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/novels/{novel_id}/material-changes", response_model=list[MaterialChangeResponse])
async def list_material_changes_route(
    novel_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    material_type: str | None = Query(default=None),
    material_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[MaterialChangeResponse]:
    await get_owned_novel(session, current_user, novel_id)
    return await list_material_changes(
        session,
        novel_id=novel_id,
        material_type=material_type,
        material_id=material_id,
        limit=limit,
    )
