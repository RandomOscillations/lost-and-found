from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from packages.common.config import get_settings
from packages.common.schemas.item import FoundItemCreate, LostItemCreate
from packages.common.schemas.subscription import SubscriptionCreate

from .proxy import forward_request
from .idempotency import ensure_idempotent

router = APIRouter(tags=["items"])


class ReportPayload(BaseModel):
    targetId: str
    reason: str


def _base() -> str:
    return get_settings().intake_service_url


@router.post("/items/lost")
async def create_lost(payload: LostItemCreate, request: Request):
    await ensure_idempotent(request, payload.model_dump(mode="json"))
    return await forward_request(
        request,
        base_url=_base(),
        path="/items/lost",
        json_body=payload,
    )


@router.post("/items/found")
async def create_found(payload: FoundItemCreate, request: Request):
    await ensure_idempotent(request, payload.model_dump(mode="json"))
    return await forward_request(
        request,
        base_url=_base(),
        path="/items/found",
        json_body=payload,
    )


@router.get("/items/{item_id}")
async def get_item(item_id: str, request: Request):
    return await forward_request(request, base_url=_base(), path=f"/items/{item_id}")


@router.get("/items")
async def list_items(request: Request):
    return await forward_request(request, base_url=_base(), path="/items")


@router.post("/reports")
async def report(payload: ReportPayload, request: Request):
    await ensure_idempotent(request, payload.model_dump(mode="json"))
    return await forward_request(
        request,
        base_url=_base(),
        path="/reports",
        json_body=payload,
    )


@router.post("/subscriptions")
async def subscribe(payload: SubscriptionCreate, request: Request):
    await ensure_idempotent(request, payload.model_dump(mode="json"))
    return await forward_request(
        request,
        base_url=_base(),
        path="/subscriptions",
        json_body=payload,
    )


@router.delete("/subscriptions")
async def unsubscribe(request: Request):
    return await forward_request(request, base_url=_base(), path="/subscriptions")
