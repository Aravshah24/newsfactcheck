from __future__ import annotations

import hashlib
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import GroundTruthClaim, GroundTruthEvidence, GroundTruthSource, VerificationVerdict

logger = logging.getLogger(__name__)


def _normalize_claim(text: str) -> str:
    """Normalize claim text for consistent hashing."""
    return " ".join(text.lower().strip().split())


def _claim_hash(text: str) -> str:
    """Generate SHA256 hash of normalized claim."""
    normalized = _normalize_claim(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def lookup_ground_truth_claim(session: Session, claim_text: str) -> GroundTruthClaim | None:
    """Look up a pre-verified ground truth claim by exact match."""
    claim_hash = _claim_hash(claim_text)
    return (
        session.query(GroundTruthClaim)
        .filter(
            GroundTruthClaim.claim_hash == claim_hash,
            GroundTruthClaim.is_active.is_(True),
        )
        .first()
    )


def lookup_ground_truth_evidence(
    session: Session, claim_text: str, document_url: str
) -> GroundTruthEvidence | None:
    """Look up pre-verified evidence for a specific claim-document pair."""
    claim_hash = _claim_hash(claim_text)
    return (
        session.query(GroundTruthEvidence)
        .filter(
            GroundTruthEvidence.claim_hash == claim_hash,
            GroundTruthEvidence.document_url == document_url,
            GroundTruthEvidence.is_active.is_(True),
        )
        .first()
    )


def apply_ground_truth_claim(
    session: Session,
    claim_text: str,
    subclaims: list,
    state: dict,
) -> dict | None:
    """Apply ground truth claim if available, returning verification results dict or None."""
    gt = lookup_ground_truth_claim(session, claim_text)
    if not gt:
        return None

    logger.info("Using ground truth claim for: %s", claim_text[:100])

    # Map ground truth verdicts to verification results format
    results = []
    subclaim_texts = gt.subclaim_texts
    verdicts = gt.verdicts
    confidences = gt.confidences

    # Match subclaims by text similarity (since IDs won't match)
    from difflib import SequenceMatcher

    for subclaim in subclaims:
        subclaim_text = getattr(subclaim, "text", str(subclaim))
        best_match_idx = 0
        best_score = 0.0
        for idx, gt_text in enumerate(subclaim_texts):
            score = SequenceMatcher(None, subclaim_text.lower(), gt_text.lower()).ratio()
            if score > best_score:
                best_score = score
                best_match_idx = idx

        if best_score < 0.7:  # Low match confidence
            continue

        verdict = verdicts[best_match_idx] if best_match_idx < len(verdicts) else "insufficient_evidence"
        confidence = confidences[best_match_idx] if best_match_idx < len(confidences) else 0.5

        results.append({
            "subclaim_id": getattr(subclaim, "id", None),
            "subclaim_text": subclaim_text,
            "verdict": verdict,
            "confidence": float(confidence),
            "calibrated_confidence": float(confidence),
            "rationale": f"Ground truth fallback (source: {gt.source})",
            "supporting_evidence_count": 0,
            "contradicting_evidence_count": 0,
            "context_evidence_count": 0,
            "independent_supporting_groups": 0,
            "independent_groups": 0,
            "role_weighted_support": 0.0,
            "role_weighted_contradiction": 0.0,
            "primary_evidence_status": "NOT_SEARCHED",
            "method": f"ground_truth_fallback_{gt.source}",
            "applied_rules": ["ground_truth_fallback"],
        })

    return {
        "ground_truth_used": True,
        "ground_truth_id": gt.id,
        "ground_truth_source": gt.source,
        "verification_results": results,
        "overall_verdict": gt.overall_verdict,
        "overall_confidence": gt.overall_confidence,
    }


def apply_ground_truth_evidence(
    session: Session,
    claim_text: str,
    document_url: str,
) -> dict | None:
    """Look up and apply ground truth evidence for a claim-document pair."""
    gt = lookup_ground_truth_evidence(session, claim_text, document_url)
    if not gt:
        return None

    logger.info("Using ground truth evidence for claim-document pair")

    return {
        "stance": gt.stance,
        "confidence": gt.confidence,
        "rationale": gt.rationale or f"Ground truth fallback (source: {gt.source})",
        "dimension_status": gt.dimension_status,
        "method": f"ground_truth_fallback_{gt.source}",
    }


def add_ground_truth_claim(
    session: Session,
    claim_text: str,
    subclaim_texts: list[str],
    verdicts: list[str],
    confidences: list[float],
    overall_verdict: str,
    overall_confidence: float,
    source: str = GroundTruthSource.MANUAL.value,
    annotated_by: str | None = None,
    evidence_refs: list[dict] | None = None,
    expires_at: datetime | None = None,
) -> GroundTruthClaim:
    """Add a new ground truth claim."""
    claim_hash = _claim_hash(claim_text)

    # Check if already exists
    existing = session.query(GroundTruthClaim).filter(GroundTruthClaim.claim_hash == claim_hash).first()
    if existing:
        # Update existing
        existing.subclaim_texts = subclaim_texts
        existing.verdicts = verdicts
        existing.confidences = confidences
        existing.overall_verdict = overall_verdict
        existing.overall_confidence = overall_confidence
        existing.source = source
        existing.annotated_by = annotated_by
        existing.evidence_refs = evidence_refs
        existing.expires_at = expires_at
        existing.is_active = True
        session.flush()
        return existing

    gt = GroundTruthClaim(
        claim_text=claim_text,
        claim_hash=claim_hash,
        subclaim_texts=subclaim_texts,
        verdicts=verdicts,
        confidences=confidences,
        overall_verdict=overall_verdict,
        overall_confidence=overall_confidence,
        source=source,
        annotated_by=annotated_by,
        evidence_refs=evidence_refs,
        expires_at=expires_at,
    )
    session.add(gt)
    session.flush()
    return gt


def add_ground_truth_evidence(
    session: Session,
    claim_text: str,
    document_url: str,
    stance: str,
    dimension_status: dict,
    confidence: float,
    document_title: str | None = None,
    rationale: str | None = None,
    source: str = GroundTruthSource.MANUAL.value,
    annotated_by: str | None = None,
    expires_at: datetime | None = None,
) -> GroundTruthEvidence:
    """Add a new ground truth evidence entry."""
    claim_hash = _claim_hash(claim_text)

    gt = GroundTruthEvidence(
        claim_text=claim_text,
        claim_hash=claim_hash,
        document_url=document_url,
        document_title=document_title,
        stance=stance,
        dimension_status=dimension_status,
        confidence=confidence,
        rationale=rationale,
        source=source,
        annotated_by=annotated_by,
        expires_at=expires_at,
    )
    session.add(gt)
    session.flush()
    return gt


# Import here to avoid circular import
from datetime import datetime