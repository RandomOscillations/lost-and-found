from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict

from .common import Location, Media


class ItemBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str
    description: str
    tags: List[str] = Field(default_factory=list)
    location: Location
    when: Optional[datetime] = None
    photos: List[Media] = Field(default_factory=list)
    category: Optional[str] = Field(default=None, description="Optional category label")


class LostItemCreate(ItemBase):
    type: str = Field(default="lost")


class FoundItemCreate(ItemBase):
    type: str = Field(default="found")
    verificationPrompts: List[str] = Field(
        default_factory=list,
        max_items=2,
        description="Custom verification prompts supplied by finder",
    )


class ItemOut(ItemBase):
    id: str
    type: str
    ownerId: Optional[str] = None
    finderId: Optional[str] = None
    status: str
    createdAt: datetime
    updatedAt: Optional[datetime] = None


class ItemSearchQuery(BaseModel):
    type: Optional[str] = None
    zone: Optional[str] = None
    tag: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None


class MatchExplanation(BaseModel):
    tags: List[str] = Field(default_factory=list)
    aspects: List[str] = Field(default_factory=list)


class MatchCandidate(BaseModel):
    itemId: str
    candidateId: str
    score: float
    explanation: MatchExplanation = Field(default_factory=MatchExplanation)
