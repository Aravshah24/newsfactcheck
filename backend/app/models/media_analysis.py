from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MediaAnalysis(Base):
    __tablename__ = "media_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    left_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    center_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    right_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    framing_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    omitted_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    publisher_distribution: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    methodology: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    claim: Mapped["Claim"] = relationship(back_populates="media_analyses")
