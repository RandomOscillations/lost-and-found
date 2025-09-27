from __future__ import annotations

from fastapi import APIRouter, Request

from packages.common.config import get_settings

from .proxy import forward_request

router = APIRouter(tags=["matches"])


@router.get("/matches")
async def matches(request: Request):
    settings = get_settings()
    return await forward_request(request, base_url=settings.vision_service_url, path="/matches")
