from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SubclaimConclusion(Base):
    """A verified conclusion, stored separately from the evidence it rests on.

    Raw evidence records what a document said. This table records what the
    system concluded from the assessed evidence, which independent source groups
    backed it, and which guard rails were applied. Keeping the two apart means a
    conclusion can never be mistaken for a retrieved fact, and every conclusion
    can be traced back to the evidence items it used.
    """

    __tablename__ = "subclaim_conclusions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    subclaim_id: Mapped[int] = mapped_column(ForeignKey("subclaims.id"), nullable=False, index=True)
    verdict: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    independent_source_groups: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    supporting_evidence_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    applied_rules: Mapped[list | None] = mapped_column(JSON, nullable=True)
    method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    claim: Mapped["Claim"] = relationship(back_populates="subclaim_conclusions")
    subclaim: Mapped["Subclaim"] = relationship(back_populates="conclusions")
