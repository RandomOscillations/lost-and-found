from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from packages.common.config import get_settings
from packages.common.db import get_db_session
from packages.common.schemas.item import MatchCandidate
from .service import VisionService

router = APIRouter(prefix="", tags=["matches"])
settings = get_settings()


@router.get("/matches", response_model=list[MatchCandidate])
async def get_matches(
    item_id: uuid.UUID = Query(..., alias="itemId"),
    k: int = Query(settings.default_match_limit, ge=1, le=settings.max_match_limit),
    session=Depends(get_db_session),
) -> list[MatchCandidate]:
    service = VisionService(session)
    try:
        return await service.get_matches(item_id, limit=k)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
