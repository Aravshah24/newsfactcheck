from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PublisherType(str, Enum):
    NEWS = "news"
    GOVERNMENT = "government"
    NGO = "ngo"
    ACADEMIC = "academic"
    SOCIAL = "social"
    OTHER = "other"


class Publisher(Base):
    __tablename__ = "publishers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    publisher_type: Mapped[PublisherType] = mapped_column(
        SAEnum(PublisherType, name="publisher_type"),
        default=PublisherType.NEWS,
        nullable=False,
    )
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    documents: Mapped[list["Document"]] = relationship(back_populates="publisher", cascade="all, delete-orphan")
