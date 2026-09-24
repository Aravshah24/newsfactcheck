from __future__ import annotations

from pydantic import BaseModel, Field


class InvestigationCreateRequest(BaseModel):
    claim: str = Field(..., min_length=1)


class InvestigationCreateResponse(BaseModel):
    claim_id: int
    status: str = "started"


class InvestigationStateResponse(BaseModel):
    claim_id: int
    claim_text: str
    status: str
    subclaims: list[dict]
    evidence_count: int = 0
    errors: list[str] = []
    overall_verdict: str | None = None
    overall_confidence: float | None = None
    report: str | None = None
    evidence: list[dict] = []
    source_independence: dict | None = None
    media_coverage: dict | None = None
    completeness: dict | None = None
    verification: list[dict] = []
