from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    verdict_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_text: Mapped[str] = mapped_column(Text, nullable=False)
    overall_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_evidence_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_independence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    retrieval_stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    llm_available: Mapped[bool | None] = mapped_column(nullable=True)
    llm_status: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    methodology_version: Mapped[str | None] = mapped_column(String(128), nullable=True)

    claim: Mapped["Claim"] = relationship(back_populates="reports")
