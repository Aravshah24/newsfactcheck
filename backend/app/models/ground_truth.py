from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GroundTruthSource(str, Enum):
    """Source of the ground truth label."""
    MANUAL = "manual"           # Human-annotated
    REGRESSION_TEST = "regression_test"  # From test suite
    HISTORICAL = "historical"   # From previous investigation runs
    EXTERNAL = "external"       # Imported from external dataset


class GroundTruthClaim(Base):
    """Pre-verified claim-evidence pair for fallback lookup.

    When LLM is unavailable or for known claims, the system can look up
    a pre-verified ground truth instead of running the full pipeline.
    """

    __tablename__ = "ground_truth_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    claim_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)  # SHA256 of normalized claim
    subclaim_texts: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    verdicts: Mapped[list[str]] = mapped_column(JSON, nullable=False)  # Per-subclaim verdicts
    confidences: Mapped[list[float]] = mapped_column(JSON, nullable=False)  # Per-subclaim confidences
    evidence_refs: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)  # Supporting evidence metadata
    overall_verdict: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    overall_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default=GroundTruthSource.MANUAL.value)
    annotated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    annotated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # For time-sensitive claims
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    __table_args__ = (
        Index("ix_ground_truth_active_hash", "is_active", "claim_hash"),
        Index("ix_ground_truth_expires", "expires_at"),
    )


class GroundTruthEvidence(Base):
    """Pre-verified evidence for specific claim-evidence pairs.

    Used for entailment fallback: if we've seen this exact (claim, document) pair
    before with a known entailment result, we can reuse it.
    """

    __tablename__ = "ground_truth_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    document_url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    document_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    document_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # For deduplication
    stance: Mapped[str] = mapped_column(String(32), nullable=False)  # supports/contradicts/context/neutral
    dimension_status: Mapped[dict] = mapped_column(JSON, nullable=False)  # Per-dimension match/conflict/absent/unclear
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default=GroundTruthSource.MANUAL.value)
    annotated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    annotated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    __table_args__ = (
        Index("ix_gt_evidence_claim_url", "claim_hash", "document_url"),
        Index("ix_gt_evidence_active", "is_active"),
    )