from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class VerificationVerdict(str, Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    DISPUTED = "disputed"
    MISLEADING_OR_INCOMPLETE = "misleading_or_incomplete"
    UNVERIFIABLE = "unverifiable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class VerificationResult(Base):
    __tablename__ = "verification_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    subclaim_id: Mapped[int] = mapped_column(ForeignKey("subclaims.id"), nullable=False, index=True)
    verdict: Mapped[str] = mapped_column(String(40), default=VerificationVerdict.INSUFFICIENT_EVIDENCE.value, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    supporting_evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    contradicting_evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    independent_evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    subclaim: Mapped["Subclaim"] = relationship(back_populates="verification_results")
