from __future__ import annotations

from pydantic import BaseModel


class SubscriptionCreate(BaseModel):
    tag: str | None = None
    zone: str | None = None


class Subscription(BaseModel):
    id: str
    tag: str | None = None
    zone: str | None = None
