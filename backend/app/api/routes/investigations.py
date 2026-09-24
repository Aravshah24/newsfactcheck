from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.graph.investigation import InvestigationGraph
from app.models import Claim
from app.schemas.investigation import InvestigationCreateRequest, InvestigationCreateResponse, InvestigationStateResponse

router = APIRouter(prefix="/api/v1", tags=["investigations"])
INVESTIGATION_STORE: dict[int, dict] = {}
logger = logging.getLogger(__name__)


@router.post("/investigations", response_model=InvestigationCreateResponse)
def create_investigation(payload: InvestigationCreateRequest, db: Session = Depends(get_db)) -> InvestigationCreateResponse:
    try:
        graph = InvestigationGraph(session_factory=lambda: db)
        result = graph.run_investigation(payload.claim, session_factory=lambda: db)

        claim = db.query(Claim).filter(Claim.claim_text == payload.claim).order_by(Claim.id.desc()).first()
        if claim is None:
            logger.exception("Investigation execution failed before persistence for claim: %s", payload.claim)
            raise HTTPException(status_code=500, detail="Investigation was not persisted.")

        INVESTIGATION_STORE[claim.id] = result
        return InvestigationCreateResponse(claim_id=claim.id, status="started")
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unhandled exception while creating investigation for claim: %s", payload.claim)
        raise HTTPException(status_code=500, detail="Investigation was not persisted.")


@router.get("/investigations/{claim_id}", response_model=InvestigationStateResponse)
def get_investigation(claim_id: int, db: Session = Depends(get_db)) -> InvestigationStateResponse:
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    stored = INVESTIGATION_STORE.get(claim_id)
    subclaims = [
        {"id": subclaim.id, "text": subclaim.text, "type": subclaim.subclaim_type}
        for subclaim in claim.subclaims
    ]

    if stored is None:
        return InvestigationStateResponse(
            claim_id=claim.id,
            claim_text=claim.claim_text,
            status=claim.status,
            subclaims=subclaims,
            evidence_count=len(claim.evidence_items),
            errors=[],
        )

    stored_subclaims = stored.get("subclaims") or subclaims
    return InvestigationStateResponse(
        claim_id=claim.id,
        claim_text=stored.get("claim_text", claim.claim_text),
        status=stored.get("status", claim.status),
        subclaims=stored_subclaims,
        evidence_count=stored.get("evidence_count", len(claim.evidence_items)),
        errors=stored.get("errors", []),
        overall_verdict=stored.get("overall_verdict", {}).get("overall_verdict") if isinstance(stored.get("overall_verdict"), dict) else None,
        overall_confidence=stored.get("overall_verdict", {}).get("overall_confidence") if isinstance(stored.get("overall_verdict"), dict) else None,
        report=stored.get("report"),
        evidence=stored.get("evidence", []),
        source_independence=stored.get("source_independence"),
        media_coverage=stored.get("media_analysis"),
        completeness=stored.get("completeness"),
        verification=stored.get("verification_results", []),
    )
