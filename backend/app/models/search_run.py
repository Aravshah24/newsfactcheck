from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SearchChannel(str, Enum):
    GDELT = "gdelt"
    WEB_SEARCH = "web_search"
    PRIMARY_SOURCE = "primary_source"
    RSS = "rss"
    OTHER = "other"


class SearchRun(Base):
    __tablename__ = "search_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    subclaim_id: Mapped[int | None] = mapped_column(ForeignKey("subclaims.id"), nullable=True, index=True)
    retrieval_channel: Mapped[str] = mapped_column(String(32), default=SearchChannel.OTHER.value, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    claim: Mapped["Claim"] = relationship(back_populates="search_runs")
    subclaim: Mapped["Subclaim | None"] = relationship(back_populates="search_runs")
