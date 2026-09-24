from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SourceType(str, Enum):
    PRIMARY = "primary"
    AUTHORITATIVE = "authoritative"
    NEWS = "news"
    SOCIAL = "social"
    OTHER = "other"


class EvidenceCategory(str, Enum):
    RAW = "raw"
    AGENT_INTERPRETATION = "agent_interpretation"
    VERIFIED_CONCLUSION = "verified_conclusion"


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    MIXED = "mixed"
    NO_EVIDENCE = "no_evidence"


class ClaimCreate(BaseModel):
    claim_text: str = Field(..., min_length=1)
    normalized_claim: str | None = None


class SourceRecordRead(BaseModel):
    id: int
    title: str | None = None
    url: str | None = None
    source_type: SourceType = SourceType.OTHER
    publication_name: str | None = None
    is_primary: bool = False
    is_authoritative: bool = False
    is_independent: bool | None = None
    provenance: str | None = None
    model_config = ConfigDict(from_attributes=True)


class EvidenceRecordRead(BaseModel):
    id: int
    claim_id: int
    source_id: int | None = None
    category: EvidenceCategory = EvidenceCategory.RAW
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    summary: str
    raw_text: str | None = None
    retrieval_channel: str | None = None
    url: str | None = None
    is_supporting: bool | None = None
    is_contradicting: bool | None = None
    provenance: str | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class VerdictSummary(BaseModel):
    claim_text: str
    overall_verdict: str = "unverified"
    support_count: int = 0
    contradict_count: int = 0
    primary_source_count: int = 0
    independence_notes: str | None = None
    completeness_notes: str | None = None
