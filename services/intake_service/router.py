from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import NoResultFound

from packages.common.db import get_db_session
from packages.common.events import bus
from packages.common.models import Item, ItemStatus, ItemType, PromptSource
from packages.common.schemas.common import APIMessage, Media
from packages.common.schemas.item import FoundItemCreate, ItemOut, ItemSearchQuery, LostItemCreate
from packages.common.schemas.subscription import Subscription, SubscriptionCreate
from packages.common.question_bank import QuestionBankService

from .dependencies import get_current_user
from .service import IntakeService

router = APIRouter(prefix="", tags=["items"])


def get_question_bank(request: Request) -> QuestionBankService:
    return request.app.state.question_bank


def serialize_item(item: Item) -> ItemOut:
    media_relationship = item.__dict__.get("media") or []
    photos = [
        Media(
            id=str(media.id),
            url=media.url,
            thumbnails=[thumb for thumb in [media.thumb_url] if thumb],
            safety={
                "facesBlurred": media.faces_blurred,
                "piiRedacted": media.pii_redacted,
            },
        )
        for media in media_relationship
    ]
    return ItemOut(
        id=str(item.id),
        type=item.type,
        title=item.title,
        description=item.description,
        tags=item.tags,
        location=item.location_raw or {},
        when=item.when,
        photos=photos,
        ownerId=str(item.owner_id) if item.owner_id else None,
        finderId=str(item.finder_id) if item.finder_id else None,
        status=item.status,
        category=item.category,
        createdAt=item.created_at,
        updatedAt=item.updated_at,
    )


@router.post("/items/lost", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def create_lost_item(
    payload: LostItemCreate,
    background: BackgroundTasks,
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
    question_bank: QuestionBankService = Depends(get_question_bank),
) -> ItemOut:
    service = IntakeService(session, question_bank)
    item = await service.create_item(
        type_=ItemType.LOST,
        title=payload.title,
        description=payload.description,
        tags=payload.tags,
        location=payload.location.model_dump(),
        when=payload.when,
        photos=[photo.model_dump() for photo in payload.photos],
        category=payload.category,
        prompts=[],
        owner_id=current_user.id,
        finder_id=None,
    )
    background.add_task(bus.publish, "items.created", {"itemId": str(item.id)})
    return serialize_item(item)


@router.post("/items/found", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def create_found_item(
    payload: FoundItemCreate,
    background: BackgroundTasks,
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
    question_bank: QuestionBankService = Depends(get_question_bank),
) -> ItemOut:
    service = IntakeService(session, question_bank)
    item = await service.create_item(
        type_=ItemType.FOUND,
        title=payload.title,
        description=payload.description,
        tags=payload.tags,
        location=payload.location.model_dump(),
        when=payload.when,
        photos=[photo.model_dump() for photo in payload.photos],
        category=payload.category,
        prompts=payload.verificationPrompts,
        owner_id=None,
        finder_id=current_user.id,
    )
    background.add_task(bus.publish, "items.created", {"itemId": str(item.id)})
    return serialize_item(item)


@router.get("/items/{item_id}", response_model=ItemOut)
async def get_item(
    item_id: uuid.UUID,
    session=Depends(get_db_session),
    question_bank: QuestionBankService = Depends(get_question_bank),
) -> ItemOut:
    service = IntakeService(session, question_bank)
    try:
        item = await service.get_item(item_id)
    except NoResultFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found") from exc
    return serialize_item(item)


@router.get("/items", response_model=list[ItemOut])
async def search_items(
    type: str | None = Query(None, description="Item type"),
    zone: str | None = Query(None),
    tag: str | None = Query(None),
    status_param: str | None = Query(None, alias="status"),
    category: str | None = Query(None),
    session=Depends(get_db_session),
    question_bank: QuestionBankService = Depends(get_question_bank),
) -> list[ItemOut]:
    service = IntakeService(session, question_bank)
    items = await service.search_items(
        type_=type,
        zone=zone,
        tag=tag,
        status=status_param,
        category=category,
    )
    return [serialize_item(item) for item in items]


@router.post("/reports", response_model=APIMessage, status_code=status.HTTP_202_ACCEPTED)
async def report_content(
    payload: dict,
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
    question_bank: QuestionBankService = Depends(get_question_bank),
) -> APIMessage:
    target_id = payload.get("targetId")
    reason = payload.get("reason")
    if not target_id or not reason:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="targetId and reason required")
    service = IntakeService(session, question_bank)
    try:
        target_uuid = uuid.UUID(target_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid targetId") from exc
    await service.record_report(current_user.id, target_uuid, reason)
    return APIMessage(message="Report accepted")


@router.post("/subscriptions", response_model=Subscription, status_code=status.HTTP_201_CREATED)
async def subscribe(
    payload: SubscriptionCreate,
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
    question_bank: QuestionBankService = Depends(get_question_bank),
) -> Subscription:
    if not payload.tag and not payload.zone:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="tag or zone required")
    service = IntakeService(session, question_bank)
    subscription = await service.create_subscription(current_user.id, payload.tag, payload.zone)
    return Subscription(id=str(subscription.id), tag=subscription.tag, zone=subscription.zone)


@router.delete("/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    id: uuid.UUID = Query(..., alias="id"),
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
    question_bank: QuestionBankService = Depends(get_question_bank),
) -> Response:
    service = IntakeService(session, question_bank)
    try:
        await service.delete_subscription(id, current_user.id)
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
