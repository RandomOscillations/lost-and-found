from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ItemType(str, PyEnum):
    LOST = "lost"
    FOUND = "found"


class ItemStatus(str, PyEnum):
    ACTIVE = "active"
    CLAIMED = "claimed"
    ARCHIVED = "archived"


class PromptSource(str, PyEnum):
    CURATED = "curated"
    CUSTOM = "custom"


class Item(Base):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(SAEnum(ItemType, name="item_type"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String()), default=list)
    category: Mapped[str | None] = mapped_column(String(64))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    finder_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(
        SAEnum(ItemStatus, name="item_status"), default=ItemStatus.ACTIVE, nullable=False
    )
    zone: Mapped[str | None] = mapped_column(String(120))
    location_lat: Mapped[float | None] = mapped_column(Float)
    location_lon: Mapped[float | None] = mapped_column(Float)
    location_raw: Mapped[dict | None] = mapped_column(JSONB)
    when: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    media: Mapped[list["ItemMedia"]] = relationship(back_populates="item", cascade="all, delete-orphan")
    prompts: Mapped[list["ItemPrompt"]] = relationship(back_populates="item", cascade="all, delete-orphan")


class ItemMedia(Base):
    __tablename__ = "item_media"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    thumb_url: Mapped[str | None] = mapped_column(String(500))
    faces_blurred: Mapped[bool] = mapped_column(default=True)
    pii_redacted: Mapped[bool] = mapped_column(default=True)

    item: Mapped[Item] = relationship(back_populates="media")


class ItemPrompt(Base):
    __tablename__ = "item_prompts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(SAEnum(PromptSource, name="prompt_source"), nullable=False)
    position: Mapped[int] = mapped_column(default=0)

    item: Mapped[Item] = relationship(back_populates="prompts")
