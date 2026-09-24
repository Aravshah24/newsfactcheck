from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentSourceType(str, Enum):
    PRIMARY = "primary"
    AUTHORITATIVE = "authoritative"
    NEWS = "news"
    PRESS_RELEASE = "press_release"
    BLOG = "blog"
    SOCIAL = "social"
    OFFICIAL = "official"
    OTHER = "other"


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("url", name="uq_documents_url"),
        UniqueConstraint("canonical_url", name="uq_documents_canonical_url"),
        Index("ix_documents_normalized_url", "normalized_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    publisher_id: Mapped[int] = mapped_column(ForeignKey("publishers.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    canonical_url: Mapped[str | None] = mapped_column(String(2048), nullable=True, index=True)
    normalized_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[DocumentSourceType] = mapped_column(
        SAEnum(
            DocumentSourceType,
            name="document_source_type",
            values_callable=lambda enum_type: [member.value for member in enum_type],
        ),
        default=DocumentSourceType.NEWS,
        nullable=False,
    )
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    publisher: Mapped["Publisher"] = relationship(back_populates="documents")
    evidence_items: Mapped[list["EvidenceItem"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    source_relationships_as_source: Mapped[list["SourceRelationship"]] = relationship(
        foreign_keys="SourceRelationship.source_document_id",
        back_populates="source_document",
        cascade="all, delete-orphan",
    )
    source_relationships_as_target: Mapped[list["SourceRelationship"]] = relationship(
        foreign_keys="SourceRelationship.target_document_id",
        back_populates="target_document",
        cascade="all, delete-orphan",
    )
