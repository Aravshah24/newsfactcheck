# Architecture overview

## High-level pipeline

User Claim
  -> Claim Analyzer
  -> GDELT search
  -> general web search
  -> primary / authoritative source search
  -> Evidence Collector
  -> Evidence Extractor
  -> supporting / contradicting evidence
  -> source and story clustering
  -> independence analysis
  -> completeness analysis
  -> verification
  -> verdict
  -> media coverage analysis
  -> evidence-constrained writer
  -> final report

## Key architectural choices

1. Retrieval channels are independent by design and are not collapsed into a single source of truth.
2. GDELT acts as one signal in a broader evidence network rather than the canonical fact source.
3. The database stores raw evidence, interpretation metadata, and verified conclusions separately.
4. Source clustering is designed to detect repeated reporting and shared-source dependencies.
5. The final writer is constrained by verified evidence and cannot invent unsupported facts.

## Data model direction

The backend maintains SQLAlchemy models for:
- claims
- evidence records
- sources
- source clusters
- verification state

Each record retains provenance and evidence status so the system can explain why a conclusion was reached.

## Frontend direction

The frontend will later provide:
- claim submission
- retrieval status tracking
- evidence review panels
- source independence and completeness summaries
- final report display

## Execution model

The project intentionally keeps the initial architecture lightweight and avoids unnecessary infrastructure. The goal is to remain operationally simple while preserving a clear path to more advanced retrieval and reasoning logic.
