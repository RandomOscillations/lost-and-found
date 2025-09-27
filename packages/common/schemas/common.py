from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Location(BaseModel):
    lat: Optional[float] = None
    lon: Optional[float] = None
    zone: Optional[str] = Field(default=None, description="Campus area or building")


class Media(BaseModel):
    id: Optional[str] = None
    url: str
    thumbnails: List[str] = Field(default_factory=list)
    safety: dict | None = None


class APIMessage(BaseModel):
    message: str


class PaginatedResponse(BaseModel):
    items: list
    total: int
