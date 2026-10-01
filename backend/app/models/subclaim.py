from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SubclaimType(str, Enum):
    FACTUAL = "factual"
    QUANTITATIVE = "quantitative"
    TEMPORAL = "temporal"
    CAUSAL = "causal"
    COMPARATIVE = "comparative"
    ATTRIBUTION = "attribution"
    PREDICTION = "prediction"
    OPINION = "opinion"
    OTHER = "other"


class Subclaim(Base):
    __tablename__ = "subclaims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    subclaim_type: Mapped[str] = mapped_column(String(30), default=SubclaimType.OTHER.value, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    claim: Mapped["Claim"] = relationship(back_populates="subclaims")
    evidence_items: Mapped[list["EvidenceItem"]] = relationship(back_populates="subclaim", cascade="all, delete-orphan")
    search_runs: Mapped[list["SearchRun"]] = relationship(back_populates="subclaim", cascade="all, delete-orphan")
    verification_results: Mapped[list["VerificationResult"]] = relationship(back_populates="subclaim", cascade="all, delete-orphan")
    conclusions: Mapped[list["SubclaimConclusion"]] = relationship(back_populates="subclaim", cascade="all, delete-orphan")
