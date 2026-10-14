from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.rate_limit import enforce_rate_limit
from app.db.session import get_db
from app.graph.investigation import InvestigationGraph
from app.models import AgentRun, Claim, CompletenessResult, EvidenceItem, MediaAnalysis, Report
from app.schemas.investigation import (
    InvestigationCreateRequest,
    InvestigationCreateResponse,
    InvestigationListItem,
    InvestigationListResponse,
    InvestigationStateResponse,
)
from app.services.llm import llm_diagnostics
from app.services.evidence_stance import normalise_stance

router = APIRouter(prefix="/api/v1", tags=["investigations"])
logger = logging.getLogger(__name__)


@router.post(
    "/investigations",
    response_model=InvestigationCreateResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
def create_investigation(
    payload: InvestigationCreateRequest, db: Session = Depends(get_db)
) -> InvestigationCreateResponse:
    """Run an investigation.

    The pipeline executes synchronously so the caller receives a finished,
    inspectable result rather than a placeholder. A long-running asynchronous
    mode can be layered on later without changing the response contract.
    """
    result = InvestigationGraph().run_investigation(payload.claim, session=db, trace_enabled=payload.trace_enabled)

    if result.get("status") == "failed" or result.get("claim_id") is None:
        logger.error("Investigation failed for claim: %s", payload.claim)
        detail = result.get("errors") or ["The investigation could not be completed."]
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail[0])

    return InvestigationCreateResponse(
        claim_id=result["claim_id"],
        status="completed",
        overall_verdict=result.get("overall_verdict", {}).get("overall_verdict"),
        llm_available=bool(result.get("llm_available", False)),
        llm_status=result.get("llm_status", {}),
        trace=result.get("trace", []),
    )


@router.get("/investigations", response_model=InvestigationListResponse)
def list_investigations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> InvestigationListResponse:
    """List stored investigations, newest first, so they can be reopened."""
    total = db.query(func.count(Claim.id)).scalar() or 0
    claims = (
        db.query(Claim)
        .order_by(Claim.created_at.desc(), Claim.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    claim_ids = [claim.id for claim in claims]

    reports: dict[int, Report] = {}
    counts: dict[int, int] = {}
    if claim_ids:
        # One query each instead of two per claim, so the list stays cheap.
        for report in (
            db.query(Report).filter(Report.claim_id.in_(claim_ids)).order_by(Report.id.asc()).all()
        ):
            reports[report.claim_id] = report
        for claim_id, count in (
            db.query(EvidenceItem.claim_id, func.count(EvidenceItem.id))
            .filter(EvidenceItem.claim_id.in_(claim_ids))
            .group_by(EvidenceItem.claim_id)
            .all()
        ):
            counts[claim_id] = count

    items = [
        InvestigationListItem(
            claim_id=claim.id,
            claim_text=claim.claim_text,
            status=claim.status,
            overall_verdict=reports[claim.id].verdict_summary if claim.id in reports else None,
            overall_confidence=reports[claim.id].overall_confidence if claim.id in reports else None,
            evidence_count=counts.get(claim.id, 0),
            created_at=claim.created_at,
        )
        for claim in claims
    ]
    return InvestigationListResponse(items=items, total=total)


@router.get("/investigations/{claim_id}", response_model=InvestigationStateResponse)
def get_investigation(claim_id: int, db: Session = Depends(get_db)) -> InvestigationStateResponse:
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found.")

    report = db.query(Report).filter(Report.claim_id == claim.id).order_by(Report.id.desc()).first()
    completeness = (
        db.query(CompletenessResult)
        .filter(CompletenessResult.claim_id == claim.id)
        .order_by(CompletenessResult.id.desc())
        .first()
    )
    media = (
        db.query(MediaAnalysis).filter(MediaAnalysis.claim_id == claim.id).order_by(MediaAnalysis.id.desc()).first()
    )

    # Collect errors from failed agent runs so they surface in the UI.
    failed_runs = (
        db.query(AgentRun)
        .filter(AgentRun.claim_id == claim.id, AgentRun.status == "failed")
        .order_by(AgentRun.id.asc())
        .all()
    )
    errors = [run.output_reference for run in failed_runs if run.output_reference]

    subclaims = sorted(claim.subclaims, key=lambda item: item.priority)
    conclusions = {conclusion.subclaim_id: conclusion for conclusion in _conclusions(db, claim.id)}

    evidence = [
        {
            "id": item.id,
            "subclaim_id": item.subclaim_id,
            "document_id": item.document_id,
            "stance": normalise_stance(item.stance),
            "confidence": item.confidence_score,
            "summary": item.summary,
            "url": item.url,
            "category": str(getattr(item.category, "value", item.category)),
            "title": document.title if document else None,
            "publisher": document.publisher.name if document and document.publisher else None,
            "publisher_domain": document.publisher.domain if document and document.publisher else None,
            "published_at": document.published_at if document else None,
            "retrieval_channel": item.retrieval_channel,
            "assessment_status": str(getattr(item.assessment_status, "value", item.assessment_status)),
            "excerpt": item.raw_excerpt,
            "source_type": (
                str(getattr(document.source_type, "value", document.source_type)) if document else None
            ),
            # Read-only provenance: what kind of witness this is, and the part it
            # was allowed to play. Absent on records written before provenance
            # existed, which is why every field is optional.
            "provenance_class": document.provenance_class if document else None,
            "role": item.role,
            "role_reason": item.role_reason,
            "role_weight": item.role_weight,
        }
        for item in claim.evidence_items
        for document in [item.document]
    ]

    # The column is nullable, so reports written before it was populated return
    # None here. Coerce it, otherwise every such investigation fails validation.
    primary_status = (report.primary_evidence_status if report else None) or "NOT_SEARCHED"

    verification = []
    for subclaim in subclaims:
        conclusion = conclusions.get(subclaim.id)
        if conclusion is None:
            continue
        verification.append(
            {
                "subclaim_id": subclaim.id,
                "subclaim_text": subclaim.text,
                "verdict": conclusion.verdict,
                "confidence": conclusion.confidence or 0.0,
                "calibrated_confidence": conclusion.calibrated_confidence,
                "rationale": conclusion.rationale or "",
                "supporting_evidence_count": _count(evidence, subclaim.id, "supports"),
                "contradicting_evidence_count": _count(evidence, subclaim.id, "contradicts"),
                "context_evidence_count": sum(
                    1
                    for item in evidence
                    if item["subclaim_id"] == subclaim.id and item["stance"] in {"context", "neutral"}
                ),
                "independent_supporting_groups": conclusion.independent_source_groups,
                "independent_groups": conclusion.independent_source_groups,
                "role_weighted_support": conclusion.role_weighted_support,
                "role_weighted_contradiction": conclusion.role_weighted_contradiction,
                "primary_evidence_status": primary_status,
                "method": conclusion.method or "unknown",
                "applied_rules": conclusion.applied_rules or [],
            }
        )

    return InvestigationStateResponse(
        claim_id=claim.id,
        claim_text=claim.claim_text,
        status=claim.status,
        subclaims=[{"id": subclaim.id, "text": subclaim.text, "type": subclaim.subclaim_type} for subclaim in subclaims],
        evidence_count=len(evidence),
        errors=errors,
        overall_verdict=report.verdict_summary if report else None,
        overall_confidence=report.overall_confidence if report else None,
        overall_explanation=report.overall_explanation if report else None,
        report=report.report_text if report else None,
        evidence=evidence,
        source_independence=report.source_independence if report else None,
        media_coverage=_media_payload(media),
        completeness=_completeness_payload(completeness),
        verification=verification,
        primary_evidence_status=primary_status,
        retrieval_stats=report.retrieval_stats if report else None,
        llm_available=bool(report.llm_available) if report else False,
        llm_status=(report.llm_status if report and report.llm_status else llm_diagnostics()),
    )


@router.delete("/investigations/{claim_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_investigation(claim_id: int, db: Session = Depends(get_db)) -> None:
    """Delete an investigation and every record that belongs to it."""
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found.")
    # ORM cascades remove subclaims, evidence, reports, conclusions, clusters,
    # agent runs and audit events. Retrieved documents are shared and stay.
    db.delete(claim)
    db.commit()


@router.post("/investigations/{claim_id}/cancel", status_code=status.HTTP_200_OK)
def cancel_investigation(claim_id: int, db: Session = Depends(get_db)) -> dict:
    """Request cancellation of a running investigation."""
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found.")
    if claim.cancel_requested:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cancellation already requested.")
    if claim.status in {ClaimStatus.VERIFIED.value, ClaimStatus.ARCHIVED.value, ClaimStatus.CANCELLED.value}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel investigation with status '{claim.status}'.",
        )
    claim.cancel_requested = True
    db.commit()
    return {"detail": "Cancellation requested. The investigation will stop at the next checkpoint."}


def _conclusions(db: Session, claim_id: int) -> list:
    from app.models import SubclaimConclusion

    return db.query(SubclaimConclusion).filter(SubclaimConclusion.claim_id == claim_id).all()


def _count(evidence: list[dict], subclaim_id: int, stance: str) -> int:
    return sum(1 for item in evidence if item["subclaim_id"] == subclaim_id and item["stance"] == stance)


def _media_payload(media: MediaAnalysis | None) -> dict | None:
    if media is None:
        return None
    return {
        "publisher_distribution": media.publisher_distribution,
        "left_coverage": media.left_coverage,
        "center_coverage": media.center_coverage,
        "right_coverage": media.right_coverage,
        "unknown_coverage": media.unknown_coverage,
        "framing_summary": media.framing_summary,
        "omitted_context": _decode_structured(media.omitted_context),
        "methodology": media.methodology,
    }


def _decode_structured(value: object) -> object:
    """Media values are stored as text; decode JSON payloads back to structures."""
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return value


def _completeness_payload(completeness: CompletenessResult | None) -> dict | None:
    if completeness is None:
        return None
    aspects = completeness.missing_aspects or {}
    return {
        "completeness_status": completeness.completeness_level,
        "missing_context": aspects.get("missing_context", []) if isinstance(aspects, dict) else [],
        "qualifications": [completeness.relevant_context] if completeness.relevant_context else [],
        "confidence": completeness.confidence,
    }
