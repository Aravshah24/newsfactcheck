from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EvidenceCategory(str, Enum):
    RAW = "raw"
    AGENT_INTERPRETATION = "agent_interpretation"
    VERIFIED_CONCLUSION = "verified_conclusion"


class EvidenceStance(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXT = "context"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class EvidenceAssessmentStatus(str, Enum):
    UNASSESSED = "unassessed"
    ASSESSED = "assessed"
    VERIFIED = "verified"
    REJECTED = "rejected"


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    subclaim_id: Mapped[int | None] = mapped_column(ForeignKey("subclaims.id"), nullable=True, index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True, index=True)
    category: Mapped[EvidenceCategory] = mapped_column(
        SAEnum(
            EvidenceCategory,
            name="evidence_category",
            native_enum=False,
            values_callable=lambda enum_type: [member.value for member in enum_type],
        ),
        default=EvidenceCategory.RAW,
        nullable=False,
    )
    stance: Mapped[EvidenceStance] = mapped_column(
        SAEnum(
            EvidenceStance,
            name="evidence_stance",
            native_enum=False,
            values_callable=lambda enum_type: [member.value for member in enum_type],
        ),
        default=EvidenceStance.UNKNOWN,
        nullable=False,
    )
    assessment_status: Mapped[EvidenceAssessmentStatus] = mapped_column(
        SAEnum(
            EvidenceAssessmentStatus,
            name="evidence_assessment_status",
            native_enum=False,
            values_callable=lambda enum_type: [member.value for member in enum_type],
        ),
        default=EvidenceAssessmentStatus.UNASSESSED,
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    raw_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieval_channel: Mapped[str | None] = mapped_column(String(128), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    claim: Mapped["Claim"] = relationship(back_populates="evidence_items")
    subclaim: Mapped["Subclaim | None"] = relationship(back_populates="evidence_items")
    document: Mapped["Document | None"] = relationship(back_populates="evidence_items")
    clusters: Mapped[list["EvidenceCluster"]] = relationship(
        back_populates="evidence_items",
        secondary="evidence_cluster_members",
    )
