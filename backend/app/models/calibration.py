from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CalibrationLabel(str, Enum):
    """Ground-truth label for a subclaim verdict."""
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    DISPUTED = "disputed"
    MISLEADING_OR_INCOMPLETE = "misleading_or_incomplete"
    UNVERIFIABLE = "unverifiable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class GroundTruthCalibration(Base):
    """Labeled example for confidence calibration.

    Each row represents a human-verified subclaim with its true verdict.
    Used to fit isotonic regression / Platt scaling on heuristic confidence.
    """

    __tablename__ = "ground_truth_calibration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    subclaim_text: Mapped[str] = mapped_column(Text, nullable=False)
    true_verdict: Mapped[str] = mapped_column(String(40), nullable=False)
    heuristic_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    heuristic_verdict: Mapped[str] = mapped_column(String(40), nullable=False)
    independent_groups: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    role_weighted_support: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False)  # e.g., "manual", "regression_test", "historical"
    annotated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    annotated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    __table_args__ = (
        Index("ix_calibration_verdict_confidence", "true_verdict", "heuristic_confidence"),
        Index("ix_calibration_active", "is_active"),
    )


class CalibrationModel(Base):
    """Persisted calibration model (isotonic regression / Platt scaling)."""

    __tablename__ = "calibration_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    model_type: Mapped[str] = mapped_column(String(32), nullable=False)  # "isotonic", "platt"
    model_data: Mapped[bytes] = mapped_column(nullable=False)  # joblib-serialized
    training_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    ece_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # Expected Calibration Error
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False)

    __table_args__ = (
        Index("ix_calibration_model_active", "is_active"),
    )