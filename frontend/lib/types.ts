/**
 * Types mirroring the backend Pydantic schemas in
 * `backend/app/schemas/investigation.py` and the payloads assembled in
 * `backend/app/api/routes/investigations.py`.
 *
 * Every value the backend can emit is optional or nullable. These types reflect
 * that: the UI must never assume a field is present.
 */

/** `EvidenceStance` values accepted by `normalise_stance`. */
export type Stance = 'supports' | 'contradicts' | 'context' | 'neutral' | 'unknown';

/** `EvidenceCategory` values. */
export type EvidenceCategory = 'raw' | 'agent_interpretation' | 'verified_conclusion';

/** `VerificationVerdict` values used per subclaim. */
export type SubclaimVerdict =
  | 'supported'
  | 'partially_supported'
  | 'disputed'
  | 'misleading_or_incomplete'
  | 'unverifiable'
  | 'insufficient_evidence';

/** Overall verdicts produced by `InvestigationGraph._overall_verdict`. */
export type OverallVerdict =
  | 'SUPPORTED'
  | 'DISPUTED'
  | 'PARTIALLY_SUPPORTED'
  | 'MISLEADING_OR_INCOMPLETE'
  | 'INSUFFICIENT_EVIDENCE';

/** `ClaimStatus` values. */
export type ClaimStatus = 'draft' | 'analyzing' | 'verified' | 'archived';

/** `CompletenessResult.completeness_level` values. */
export type CompletenessStatus =
  | 'COMPLETE'
  | 'MOSTLY_COMPLETE'
  | 'INCOMPLETE'
  | 'MISLEADING_BY_OMISSION';

/** `DocumentSourceType` values. */
export type SourceType =
  | 'primary'
  | 'authoritative'
  | 'news'
  | 'press_release'
  | 'blog'
  | 'social'
  | 'official'
  | 'other';

/** Values the backend may return that are not enumerated above. */
type Loose = string & Record<never, never>;

export interface InvestigationCreateRequest {
  claim: string;
}

export interface InvestigationCreateResponse {
  claim_id: number;
  status: string;
  overall_verdict: OverallVerdict | Loose | null;
  llm_available: boolean;
  llm_status: LlmStatus;
}

export interface EvidenceItem {
  id: number | null;
  subclaim_id: number | null;
  document_id: number | null;
  stance: Stance | Loose;
  confidence: number | null;
  summary: string | null;
  url: string | null;
  category: EvidenceCategory | Loose | null;
  title?: string | null;
  publisher?: string | null;
  publisher_domain?: string | null;
  published_at?: string | null;
  retrieval_channel?: string | null;
  assessment_status?: string | null;
  excerpt?: string | null;
  source_type?: SourceType | Loose | null;
}

export interface Subclaim {
  id: number | null;
  text: string;
  type: string;
}

export interface VerificationView {
  subclaim_id: number | null;
  subclaim_text: string | null;
  verdict: SubclaimVerdict | Loose;
  confidence: number;
  rationale: string;
  supporting_evidence_count: number;
  contradicting_evidence_count: number;
  context_evidence_count: number;
  independent_supporting_groups: number;
  independent_groups: number;
  primary_evidence_status: string;
  method: string;
  applied_rules: string[];
}

export interface IndependenceGroup {
  group_id: number;
  document_ids: number[];
  document_count: number;
  publishers: string[] | null;
  is_primary_or_official: boolean;
}

export interface SourceIndependence {
  documents_found: number;
  distinct_publishers: number;
  evidence_items: number;
  evidence_clusters: number;
  independent_groups: number;
  estimated_independent_sources: number;
  duplicate_derived_documents: number;
  dependency_edges: number;
  groups: IndependenceGroup[] | null;
  /** Maps a stringified evidence id to its independence group id. */
  group_for_evidence: Record<string, number> | null;
}

export interface MediaCoverage {
  publisher_distribution: Record<string, number> | null;
  left_coverage: number;
  center_coverage: number;
  right_coverage: number;
  framing_summary: string | null;
  omitted_context: string[] | string | null;
  methodology: string | null;
}

export interface CompletenessSummary {
  completeness_status: CompletenessStatus | Loose;
  missing_context: string[] | null;
  qualifications: string[] | null;
  confidence: number | null;
}

export interface RetrievalStats {
  search_runs: number;
  raw_documents: number;
  unique_documents: number;
}

export interface LlmStatus {
  provider: string | null;
  model: string | null;
  fallback_models: string[] | null;
  key_configured: boolean;
  available: boolean;
  error_code: string | null;
  error: string | null;
  remediation: string | null;
}

export interface InvestigationStateResponse {
  claim_id: number;
  claim_text: string;
  status: ClaimStatus | Loose;
  subclaims: Subclaim[];
  evidence_count: number;
  errors: string[];
  overall_verdict: OverallVerdict | Loose | null;
  overall_confidence: number | null;
  overall_explanation: string | null;
  report: string | null;
  evidence: EvidenceItem[];
  source_independence: SourceIndependence | null;
  media_coverage: MediaCoverage | null;
  completeness: CompletenessSummary | null;
  verification: VerificationView[];
  primary_evidence_status: string;
  retrieval_stats: RetrievalStats | null;
  llm_available: boolean;
  llm_status: LlmStatus;
}

export interface ServiceHealth {
  status: string;
  service: string;
  environment: string;
  llm: LlmStatus;
}
