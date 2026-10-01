from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InvestigationCreateRequest(BaseModel):
    claim: str = Field(..., min_length=1, max_length=4000)


class InvestigationCreateResponse(BaseModel):
    claim_id: int
    status: str = "completed"
    overall_verdict: str | None = None
    llm_available: bool = True
    llm_status: dict = Field(default_factory=dict)


class EvidenceView(BaseModel):
    id: int | None = None
    subclaim_id: int | None = None
    document_id: int | None = None
    stance: str = "unknown"
    confidence: float | None = None
    summary: str | None = None
    url: str | None = None
    category: str | None = None
    # Source provenance. All optional: retrieval can succeed with a partial record.
    title: str | None = None
    publisher: str | None = None
    publisher_domain: str | None = None
    published_at: datetime | None = None
    retrieval_channel: str | None = None
    assessment_status: str | None = None
    excerpt: str | None = None
    source_type: str | None = None


class VerificationView(BaseModel):
    subclaim_id: int | None = None
    subclaim_text: str | None = None
    verdict: str = "insufficient_evidence"
    confidence: float = 0.0
    rationale: str = ""
    supporting_evidence_count: int = 0
    contradicting_evidence_count: int = 0
    context_evidence_count: int = 0
    independent_supporting_groups: int = 0
    independent_groups: int = 0
    primary_evidence_status: str = "NOT_SEARCHED"
    method: str = "unknown"
    applied_rules: list[str] = Field(default_factory=list)


class InvestigationStateResponse(BaseModel):
    claim_id: int
    claim_text: str
    status: str
    subclaims: list[dict] = Field(default_factory=list)
    evidence_count: int = 0
    errors: list[str] = Field(default_factory=list)
    overall_verdict: str | None = None
    overall_confidence: float | None = None
    overall_explanation: str | None = None
    report: str | None = None
    evidence: list[EvidenceView] = Field(default_factory=list)
    source_independence: dict | None = None
    media_coverage: dict | None = None
    completeness: dict | None = None
    verification: list[VerificationView] = Field(default_factory=list)
    primary_evidence_status: str = "NOT_SEARCHED"
    retrieval_stats: dict | None = None
    llm_available: bool = False
    llm_status: dict = Field(default_factory=dict)
