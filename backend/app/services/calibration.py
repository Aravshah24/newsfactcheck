from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from sqlalchemy.orm import Session

from app.models import CalibrationLabel, CalibrationModel, GroundTruthCalibration, VerificationResult, VerificationVerdict

logger = logging.getLogger(__name__)

_MODEL_DIR = Path(__file__).resolve().parents[2] / "calibration_models"
_MODEL_DIR.mkdir(exist_ok=True)


class ConfidenceCalibrator:
    """Fit and apply confidence calibration models.

    Supports:
    - Isotonic regression (non-parametric, monotonic)
    - Platt scaling (logistic regression on confidence)
    """

    def __init__(self, session: Session):
        self.session = session
        self._model: IsotonicRegression | CalibratedClassifierCV | None = None
        self._model_type: str | None = None

    def load_active_model(self) -> bool:
        """Load the active calibration model from database."""
        model_row = (
            self.session.query(CalibrationModel)
            .filter(CalibrationModel.is_active.is_(True))
            .order_by(CalibrationModel.created_at.desc())
            .first()
        )
        if not model_row:
            return False
        try:
            self._model = joblib.loads(model_row.model_data)
            self._model_type = model_row.model_type
            logger.info("Loaded %s calibration model (trained on %d samples)", model_row.model_type, model_row.training_samples)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load calibration model: %s", exc)
            return False

    def train(self, model_type: str = "isotonic", min_samples: int = 50) -> CalibrationModel | None:
        """Train a new calibration model on active labeled data."""
        rows = (
            self.session.query(GroundTruthCalibration)
            .filter(GroundTruthCalibration.is_active.is_(True))
            .all()
        )
        if len(rows) < min_samples:
            logger.warning("Insufficient calibration data: %d samples (need %d)", len(rows), min_samples)
            return None

        # Prepare features: heuristic confidence + metadata
        X = np.array([[r.heuristic_confidence, r.independent_groups, r.role_weighted_support or 0.0] for r in rows])
        y = np.array([1 if r.true_verdict in {CalibrationLabel.SUPPORTED.value, CalibrationLabel.PARTIALLY_SUPPORTED.value} else 0 for r in rows])

        if model_type == "isotonic":
            # Isotonic regression on confidence only (1D)
            model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            model.fit(X[:, 0], y)
        elif model_type == "platt":
            # Platt scaling (logistic regression on confidence)
            base = LogisticRegression(solver="lbfgs", max_iter=1000)
            model = CalibratedClassifierCV(base, method="sigmoid", cv=3)
            model.fit(X, y)
        else:
            raise ValueError(f"Unknown model_type: {model_type}")

        # Evaluate on training data (for ECE estimate)
        if model_type == "isotonic":
            probs = model.predict(X[:, 0])
        else:
            probs = model.predict_proba(X)[:, 1]

        ece = self._expected_calibration_error(y, probs)
        logger.info("Trained %s model on %d samples, ECE=%.4f", model_type, len(rows), ece)

        # Persist
        model_bytes = joblib.dumps(model)
        model_row = CalibrationModel(
            model_type=model_type,
            model_data=model_bytes,
            training_samples=len(rows),
            ece_score=ece,
            is_active=True,
        )
        # Deactivate old models
        self.session.query(CalibrationModel).filter(CalibrationModel.is_active.is_(True)).update({CalibrationModel.is_active: False})
        self.session.add(model_row)
        self.session.flush()

        # Load into memory
        self._model = model
        self._model_type = model_type
        return model_row

    def calibrate(self, heuristic_confidence: float, independent_groups: int = 0, role_weighted_support: float = 0.0) -> float | None:
        """Apply calibration to a heuristic confidence score."""
        if self._model is None:
            if not self.load_active_model():
                return None

        try:
            if self._model_type == "isotonic":
                calibrated = float(self._model.predict(np.array([heuristic_confidence])))
            else:
                X = np.array([[heuristic_confidence, independent_groups, role_weighted_support]])
                calibrated = float(self._model.predict_proba(X)[0, 1])
            return max(0.0, min(1.0, calibrated))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Calibration failed: %s", exc)
            return None

    def calibrate_verdict(self, verdict: str, heuristic_confidence: float, independent_groups: int = 0, role_weighted_support: float = 0.0) -> tuple[str, float]:
        """Calibrate confidence for a verdict, potentially adjusting verdict label."""
        calibrated = self.calibrate(heuristic_confidence, independent_groups, role_weighted_support)
        if calibrated is None:
            return verdict, heuristic_confidence

        # For insufficient_evidence/unverifiable, cap calibrated confidence
        if verdict in {VerificationVerdict.INSUFFICIENT_EVIDENCE.value, VerificationVerdict.UNVERIFIABLE.value}:
            calibrated = min(calibrated, 0.45)
        return verdict, round(calibrated, 2)

    @staticmethod
    def _expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
        """Compute Expected Calibration Error (ECE)."""
        bins = np.linspace(0.0, 1.0, n_bins + 1)
        ece = 0.0
        for i in range(n_bins):
            mask = (y_prob >= bins[i]) & (y_prob < bins[i + 1])
            if i == n_bins - 1:
                mask = (y_prob >= bins[i]) & (y_prob <= bins[i + 1])
            if not np.any(mask):
                continue
            bin_conf = np.mean(y_prob[mask])
            bin_acc = np.mean(y_true[mask])
            ece += np.abs(bin_conf - bin_acc) * np.sum(mask)
        return float(ece / len(y_true))


def add_calibration_label(
    session: Session,
    claim_text: str,
    subclaim_text: str,
    true_verdict: str,
    heuristic_confidence: float,
    heuristic_verdict: str,
    independent_groups: int,
    role_weighted_support: float | None,
    source: str,
    annotated_by: str | None = None,
) -> GroundTruthCalibration:
    """Add a labeled example for calibration training."""
    label = GroundTruthCalibration(
        claim_text=claim_text,
        subclaim_text=subclaim_text,
        true_verdict=true_verdict,
        heuristic_confidence=heuristic_confidence,
        heuristic_verdict=heuristic_verdict,
        independent_groups=independent_groups,
        role_weighted_support=role_weighted_support,
        source=source,
        annotated_by=annotated_by,
    )
    session.add(label)
    session.flush()
    return label