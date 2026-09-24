from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ClaimStatus(str, Enum):
    DRAFT = "draft"
    ANALYZING = "analyzing"
    VERIFIED = "verified"
    ARCHIVED = "archived"


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_claim: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=ClaimStatus.DRAFT.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    subclaims: Mapped[list["Subclaim"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    evidence_items: Mapped[list["EvidenceItem"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    search_runs: Mapped[list["SearchRun"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    evidence_clusters: Mapped[list["EvidenceCluster"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    completeness_results: Mapped[list["CompletenessResult"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    media_analyses: Mapped[list["MediaAnalysis"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
