from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import CharacterState, CreativeAsset, RelationshipEdge, TimelineEvent, User
from app.schemas.materials import (
    CharacterStateCreate,
    CharacterStateResponse,
    CreativeAssetCreate,
    CreativeAssetResponse,
    RelationshipEdgeCreate,
    RelationshipEdgeResponse,
    TimelineEventCreate,
    TimelineEventResponse,
)
from app.services.novels import get_owned_novel
from app.services.rag import index_text

router = APIRouter(tags=["materials"])


@router.post("/novels/{novel_id}/creative-assets", response_model=CreativeAssetResponse, status_code=status.HTTP_201_CREATED)
async def create_creative_asset(
    novel_id: UUID,
    payload: CreativeAssetCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CreativeAsset:
    await get_owned_novel(session, current_user, novel_id)
    asset = CreativeAsset(
        novel_id=novel_id,
        asset_type=payload.asset_type,
        name=payload.name,
        summary=payload.summary,
        extra_metadata=payload.metadata,
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


@router.post("/novels/{novel_id}/timeline-events", response_model=TimelineEventResponse, status_code=status.HTTP_201_CREATED)
async def create_timeline_event(
    novel_id: UUID,
    payload: TimelineEventCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TimelineEvent:
    await get_owned_novel(session, current_user, novel_id)
    event = TimelineEvent(
        novel_id=novel_id,
        title=payload.title,
        event_time=payload.event_time,
        summary=payload.summary,
        extra_metadata=payload.metadata,
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
    return list(await session.scalars(select(TimelineEvent).where(TimelineEvent.novel_id == novel_id)))


@router.post("/novels/{novel_id}/character-states", response_model=CharacterStateResponse, status_code=status.HTTP_201_CREATED)
async def create_character_state(
    novel_id: UUID,
    payload: CharacterStateCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CharacterState:
    await get_owned_novel(session, current_user, novel_id)
    state = CharacterState(
        novel_id=novel_id,
        character_name=payload.character_name,
        state=payload.state,
        scope=payload.scope,
        extra_metadata=payload.metadata,
    )
    session.add(state)
    await session.flush()
    await index_text(
        session,
        novel_id=novel_id,
        source_type="character_state",
        source_id=str(state.id),
        text=f"{state.character_name} [{state.scope}]: {state.state}",
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
    return list(await session.scalars(select(CharacterState).where(CharacterState.novel_id == novel_id)))


@router.post("/novels/{novel_id}/relationship-edges", response_model=RelationshipEdgeResponse, status_code=status.HTTP_201_CREATED)
async def create_relationship_edge(
    novel_id: UUID,
    payload: RelationshipEdgeCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RelationshipEdge:
    await get_owned_novel(session, current_user, novel_id)
    edge = RelationshipEdge(
        novel_id=novel_id,
        source_character=payload.source_character,
        target_character=payload.target_character,
        relationship_type=payload.relationship_type,
        description=payload.description,
        extra_metadata=payload.metadata,
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
