from __future__ import annotations

from fastapi import APIRouter, Query, Request

from packages.common.config import get_settings

from .proxy import forward_request

router = APIRouter(tags=["matches"])


@router.get("/matches")
async def matches(
    request: Request,
    item_id: str = Query(..., alias="itemId"),
    k: int = Query(None, alias="k"),
):
    settings = get_settings()
    return await forward_request(
        request,
        base_url=settings.vision_service_url,
        path="/matches",
        query_params={"itemId": item_id, **({"k": k} if k is not None else {})},
    )
