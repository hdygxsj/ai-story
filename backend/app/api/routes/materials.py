from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import (
    CharacterAttribute,
    CharacterState,
    CreativeAsset,
    InventoryItem,
    MapLocation,
    RelationshipEdge,
    TimelineEvent,
    User,
)
from app.schemas.materials import (
    CharacterAttributeCreate,
    CharacterAttributeResponse,
    CharacterAttributeUpdate,
    CharacterStateCreate,
    CharacterStateResponse,
    CharacterStateUpdate,
    CreativeAssetCreate,
    CreativeAssetResponse,
    CreativeAssetUpdate,
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
    MapLocationCreate,
    MapLocationResponse,
    MapLocationUpdate,
    MaterialChangeResponse,
    RelationshipEdgeCreate,
    RelationshipEdgeResponse,
    RelationshipEdgeUpdate,
    TimelineEventCreate,
    TimelineEventReorder,
    TimelineEventResponse,
    TimelineEventUpdate,
)
from app.services.materials import (
    create_character_state,
    create_creative_asset,
    create_relationship_edge,
    create_timeline_event,
    deduplicate_character_states,
    delete_character_attribute,
    delete_character_state,
    delete_creative_asset,
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
    update_character_attribute,
    update_character_state_record,
    update_creative_asset,
    update_inventory_item,
    update_map_location,
    update_relationship_edge,
    update_timeline_event,
    upsert_character_attribute,
    upsert_inventory_item,
    upsert_map_location,
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
        position=payload.position,
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
        position=payload.position,
        metadata=payload.metadata,
        actor_source="user",
    )
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="时间线事件不存在。")
    await session.commit()
    await session.refresh(event)
    return event


@router.post("/novels/{novel_id}/timeline-events/reorder", response_model=list[TimelineEventResponse])
async def reorder_timeline_events_route(
    novel_id: UUID,
    payload: TimelineEventReorder,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[TimelineEvent]:
    await get_owned_novel(session, current_user, novel_id)
    events = await reorder_timeline_events(
        session,
        novel_id=novel_id,
        event_ids=payload.event_ids,
        actor_source="user",
    )
    if events is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="时间线事件不存在。")
    await session.commit()
    return prepare_timeline_events(events)


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


@router.post(
    "/novels/{novel_id}/character-attributes",
    response_model=CharacterAttributeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_character_attribute_route(
    novel_id: UUID,
    payload: CharacterAttributeCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CharacterAttribute:
    await get_owned_novel(session, current_user, novel_id)
    attribute = await upsert_character_attribute(
        session,
        novel_id=novel_id,
        character_name=payload.character_name,
        attribute_key=payload.attribute_key,
        value=payload.value,
        unit=payload.unit,
        scope=payload.scope,
        metadata=payload.metadata,
        actor_source="user",
    )
    await session.commit()
    await session.refresh(attribute)
    return attribute


@router.get("/novels/{novel_id}/character-attributes", response_model=list[CharacterAttributeResponse])
async def list_character_attributes_route(
    novel_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    character_name: str | None = Query(default=None),
    scope: str | None = Query(default=None),
) -> list[CharacterAttribute]:
    await get_owned_novel(session, current_user, novel_id)
    return await list_character_attributes(
        session,
        novel_id=novel_id,
        character_name=character_name,
        scope=scope,
    )


@router.patch(
    "/novels/{novel_id}/character-attributes/{attribute_id}",
    response_model=CharacterAttributeResponse,
)
async def update_character_attribute_route(
    novel_id: UUID,
    attribute_id: UUID,
    payload: CharacterAttributeUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CharacterAttribute:
    await get_owned_novel(session, current_user, novel_id)
    attribute = await update_character_attribute(
        session,
        novel_id=novel_id,
        attribute_id=attribute_id,
        character_name=payload.character_name,
        attribute_key=payload.attribute_key,
        value=payload.value,
        unit=payload.unit,
        scope=payload.scope,
        metadata=payload.metadata,
        actor_source="user",
    )
    if attribute is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色属性不存在。")
    await session.commit()
    await session.refresh(attribute)
    return attribute


@router.delete("/novels/{novel_id}/character-attributes/{attribute_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character_attribute_route(
    novel_id: UUID,
    attribute_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await get_owned_novel(session, current_user, novel_id)
    deleted = await delete_character_attribute(
        session,
        novel_id=novel_id,
        attribute_id=attribute_id,
        actor_source="user",
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色属性不存在。")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/novels/{novel_id}/inventory-items", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED)
async def upsert_inventory_item_route(
    novel_id: UUID,
    payload: InventoryItemCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> InventoryItem:
    await get_owned_novel(session, current_user, novel_id)
    item = await upsert_inventory_item(
        session,
        novel_id=novel_id,
        owner_name=payload.owner_name,
        item_name=payload.item_name,
        quantity=payload.quantity,
        unit=payload.unit,
        location_name=payload.location_name,
        description=payload.description,
        metadata=payload.metadata,
        actor_source="user",
    )
    await session.commit()
    await session.refresh(item)
    return item


@router.get("/novels/{novel_id}/inventory-items", response_model=list[InventoryItemResponse])
async def list_inventory_items_route(
    novel_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    owner_name: str | None = Query(default=None),
    location_name: str | None = Query(default=None),
) -> list[InventoryItem]:
    await get_owned_novel(session, current_user, novel_id)
    return await list_inventory_items(
        session,
        novel_id=novel_id,
        owner_name=owner_name,
        location_name=location_name,
    )


@router.patch("/novels/{novel_id}/inventory-items/{item_id}", response_model=InventoryItemResponse)
async def update_inventory_item_route(
    novel_id: UUID,
    item_id: UUID,
    payload: InventoryItemUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> InventoryItem:
    await get_owned_novel(session, current_user, novel_id)
    item = await update_inventory_item(
        session,
        novel_id=novel_id,
        item_id=item_id,
        owner_name=payload.owner_name,
        item_name=payload.item_name,
        quantity=payload.quantity,
        unit=payload.unit,
        location_name=payload.location_name,
        description=payload.description,
        metadata=payload.metadata,
        actor_source="user",
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="背包物品不存在。")
    await session.commit()
    await session.refresh(item)
    return item


@router.delete("/novels/{novel_id}/inventory-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_inventory_item_route(
    novel_id: UUID,
    item_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await get_owned_novel(session, current_user, novel_id)
    deleted = await delete_inventory_item(
        session,
        novel_id=novel_id,
        item_id=item_id,
        actor_source="user",
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="背包物品不存在。")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/novels/{novel_id}/map-locations", response_model=MapLocationResponse, status_code=status.HTTP_201_CREATED)
async def upsert_map_location_route(
    novel_id: UUID,
    payload: MapLocationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MapLocation:
    await get_owned_novel(session, current_user, novel_id)
    location = await upsert_map_location(
        session,
        novel_id=novel_id,
        name=payload.name,
        location_type=payload.location_type,
        summary=payload.summary,
        parent_name=payload.parent_name,
        coordinates=payload.coordinates,
        adjacent_location_names=payload.adjacent_location_names,
        metadata=payload.metadata,
        actor_source="user",
    )
    await session.commit()
    await session.refresh(location)
    return location


@router.get("/novels/{novel_id}/map-locations", response_model=list[MapLocationResponse])
async def list_map_locations_route(
    novel_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    location_type: str | None = Query(default=None),
    parent_name: str | None = Query(default=None),
) -> list[MapLocation]:
    await get_owned_novel(session, current_user, novel_id)
    return await list_map_locations(
        session,
        novel_id=novel_id,
        location_type=location_type,
        parent_name=parent_name,
    )


@router.patch("/novels/{novel_id}/map-locations/{location_id}", response_model=MapLocationResponse)
async def update_map_location_route(
    novel_id: UUID,
    location_id: UUID,
    payload: MapLocationUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MapLocation:
    await get_owned_novel(session, current_user, novel_id)
    location = await update_map_location(
        session,
        novel_id=novel_id,
        location_id=location_id,
        name=payload.name,
        location_type=payload.location_type,
        summary=payload.summary,
        parent_name=payload.parent_name,
        coordinates=payload.coordinates,
        adjacent_location_names=payload.adjacent_location_names,
        metadata=payload.metadata,
        actor_source="user",
    )
    if location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="地图地点不存在。")
    await session.commit()
    await session.refresh(location)
    return location


@router.delete("/novels/{novel_id}/map-locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_map_location_route(
    novel_id: UUID,
    location_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await get_owned_novel(session, current_user, novel_id)
    deleted = await delete_map_location(
        session,
        novel_id=novel_id,
        location_id=location_id,
        actor_source="user",
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="地图地点不存在。")
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
