from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import NoResultFound

from ...core.db import get_db_session
from ...schemas.claim import Claim as ClaimSchema
from ...schemas.claim import ClaimCreate, ClaimUpdate, Message as MessageSchema, MessageCreate
from ..auth.dependencies import get_current_user
from .service import ClaimsService

router = APIRouter(prefix="", tags=["claims"])


def serialize_claim(claim) -> ClaimSchema:
    return ClaimSchema(
        id=str(claim.id),
        itemId=str(claim.item_id),
        candidateId=str(claim.candidate_id),
        claimantId=str(claim.claimant_id),
        finderId=str(claim.finder_id),
        status=claim.status,
        createdAt=claim.created_at,
        updatedAt=claim.updated_at,
    )


def serialize_message(message) -> MessageSchema:
    return MessageSchema(
        id=str(message.id),
        threadId=str(message.thread_id),
        senderId=str(message.sender_id),
        body=message.body,
        createdAt=message.created_at,
    )


@router.post("/claims", response_model=ClaimSchema, status_code=status.HTTP_201_CREATED)
async def open_claim(
    payload: ClaimCreate,
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
) -> ClaimSchema:
    service = ClaimsService(session)
    claim = await service.open_claim(
        lost_item_id=uuid.UUID(payload.itemId),
        candidate_item_id=uuid.UUID(payload.candidateId),
        claimant_id=current_user.id,
        answers=payload.answers,
    )
    return serialize_claim(claim)


@router.get("/claims/{claim_id}", response_model=ClaimSchema)
async def get_claim(
    claim_id: uuid.UUID,
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
) -> ClaimSchema:
    service = ClaimsService(session)
    try:
        claim = await service.get_claim(claim_id)
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    if current_user.role != "moderator" and current_user.id not in {claim.claimant_id, claim.finder_id}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    return serialize_claim(claim)


@router.patch("/claims/{claim_id}", response_model=ClaimSchema)
async def update_claim(
    claim_id: uuid.UUID,
    payload: ClaimUpdate,
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
) -> ClaimSchema:
    service = ClaimsService(session)
    claim = await service.update_status(claim_id, current_user.id, payload.action)
    return serialize_claim(claim)


@router.get("/threads/{thread_id}/messages", response_model=list[MessageSchema])
async def list_messages(
    thread_id: uuid.UUID,
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
) -> list[MessageSchema]:
    service = ClaimsService(session)
    messages = await service.list_messages(thread_id, current_user.id)
    return [serialize_message(msg) for msg in messages]


@router.post("/threads/{thread_id}/messages", response_model=MessageSchema, status_code=status.HTTP_201_CREATED)
async def post_message(
    thread_id: uuid.UUID,
    payload: MessageCreate,
    session=Depends(get_db_session),
    current_user=Depends(get_current_user),
) -> MessageSchema:
    service = ClaimsService(session)
    message = await service.post_message(thread_id, current_user.id, payload.body)
    return serialize_message(message)
