from __future__ import annotations

from fastapi import APIRouter, Request

from packages.common.config import get_settings

from .proxy import forward_request

router = APIRouter(tags=["items"])


def _base() -> str:
    return get_settings().intake_service_url


@router.post("/items/lost")
async def create_lost(request: Request):
    return await forward_request(request, base_url=_base(), path="/items/lost")


@router.post("/items/found")
async def create_found(request: Request):
    return await forward_request(request, base_url=_base(), path="/items/found")


@router.get("/items/{item_id}")
async def get_item(item_id: str, request: Request):
    return await forward_request(request, base_url=_base(), path=f"/items/{item_id}")


@router.get("/items")
async def list_items(request: Request):
    return await forward_request(request, base_url=_base(), path="/items")


@router.post("/reports")
async def report(request: Request):
    return await forward_request(request, base_url=_base(), path="/reports")


@router.post("/subscriptions")
async def subscribe(request: Request):
    return await forward_request(request, base_url=_base(), path="/subscriptions")


@router.delete("/subscriptions")
async def unsubscribe(request: Request):
    return await forward_request(request, base_url=_base(), path="/subscriptions")
