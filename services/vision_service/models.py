from __future__ import annotations

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class VisionBase(DeclarativeBase):
    pass


class Embedding(VisionBase):
    __tablename__ = "embeddings"

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    modality: Mapped[str] = mapped_column(String(16), primary_key=True, default="text")
    vec: Mapped[list[float]] = mapped_column(Vector(512))

