from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, Enum as SAEnum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SourceRelationshipType(str, Enum):
    SYNDICATED_FROM = "syndicated_from"
    COPIED_FROM = "copied_from"
    QUOTES = "quotes"
    CITES = "cites"
    TRANSLATES = "translates"
    UPDATES = "updates"
    RELATED = "related"
    UNKNOWN = "unknown"


class SourceRelationship(Base):
    __tablename__ = "source_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_document_id",
            "target_document_id",
            "relationship_type",
            name="uq_source_relationships_pair_type",
        ),
        CheckConstraint("source_document_id != target_document_id", name="ck_source_relationships_no_self_loop"),
        Index("ix_source_relationships_source_target", "source_document_id", "target_document_id"),
        Index("ix_source_relationships_target_source", "target_document_id", "source_document_id"),
        Index("ix_source_relationships_relationship_type", "relationship_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    target_document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    relationship_type: Mapped[SourceRelationshipType] = mapped_column(
        SAEnum(SourceRelationshipType, name="source_relationship_type"),
        default=SourceRelationshipType.UNKNOWN,
        nullable=False,
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    source_document: Mapped["Document"] = relationship(
        foreign_keys=[source_document_id],
        back_populates="source_relationships_as_source",
    )
    target_document: Mapped["Document"] = relationship(
        foreign_keys=[target_document_id],
        back_populates="source_relationships_as_target",
    )
