# NewsFactCheck

## What this project does

NewsFactCheck is a local fact-checking system that takes a news claim, decomposes
it into atomic subclaims, retrieves candidate documents, assesses each document
against the **complete proposition** of the subclaim, weighs the result by how
many genuinely independent sources produced it, and produces a structured report
with a transparent verdict and explicit uncertainty.

The central rule of the system is:

```
RETRIEVED DOCUMENT  !=  EVIDENCE  !=  SUPPORTING EVIDENCE
```

A document being about the same topic does **not** mean it supports the claim.
Evidence is compared dimension by dimension: subject, action, object or
location, date, quantity, polarity, and qualifiers. A conflict on any dimension
is a contradiction. Missing coverage of a dimension the claim specifies is
context, not support. Support requires a match on every specified dimension.

## Architecture

Claim
-> Claim Analyzer (atomic subclaims)
-> Proposition extraction (dimensions per subclaim)
-> Source Discovery / Opposition / Primary Evidence
-> Deduplication and syndication detection
-> Evidence Extraction (dimension-by-dimension assessment)
-> Independence grouping and clustering
-> Completeness
-> Verification (model proposes, guard rails dispose)
-> Media Analysis
-> Writer

See `docs/architecture.md` for the full description, the dimension model, and
the verification guard rails.

## Agents

- **Claim Analyzer** - splits a claim into atomic, independently checkable
  subclaims.
- **Proposition Extractor** - decomposes each subclaim into comparable
  dimensions. This is general linguistic decomposition; there are no domain- or
  entity-specific rules.
- **Source Discovery** - generates queries and normalises candidate documents
  across independent retrieval channels.
- **Opposition Agent** - searches for corrections, denials, differing figures or
  dates, narrower scopes, and official records that disagree.
- **Primary Source Retriever** - looks for official and institutional records,
  and reports `FOUND`, `NOT_FOUND`, `SEARCH_FAILED`, or `NOT_CONFIGURED`
  distinctly.
- **Evidence Extractor** - compares a document against the complete proposition
  and records the stance plus the per-dimension analysis. Topical relevance alone
  never yields support.
- **Completeness Agent** - identifies missing context, qualifiers, and omission
  risks.
- **Verification Agent** - determines supported / partially supported / disputed
  / insufficient evidence, subject to deterministic guard rails.
- **Media Analysis** - summarises publisher distribution and framing. It never
  contributes to a verdict.
- **Writer** - renders the report using the evidence actually retrieved, and
  cannot change a computed verdict.

## Why opposition exists

If we only search for reporting that matches the original claim, we may miss the
most important reason to doubt it. The opposition pass searches for corrections,
disputed timelines, missing qualifications, contradictory numbers, and official
records that disagree. Its results are documents, not verdicts: they go through
the same propositional assessment as everything else.

## Why source independence matters

Ten articles from one syndicated report are not ten independent confirmations.
Documents are grouped into independence groups using recorded source
relationships, shared content hashes, and shared publishers. Confidence is
capped by the number of independent groups that produced supporting evidence,
not by the number of articles retrieved.

## Completeness

A claim can be factually supported and still incomplete or misleading.
Completeness analysis checks for missing comparisons, omitted baselines, missing
time periods, broad causal language, and qualifications the audience would need.

## Media analysis

Media analysis is separate from verification. It summarises publisher
distribution and framing. Publisher orientation is a distribution-level
description and is never evidence for or against a claim.

## Requirements

- Python 3.11+
- PostgreSQL
- A Gemini or OpenAI API key (required for live propositional reasoning; the
  system reports clearly when it is unavailable and never fabricates results)

## Running locally

### Backend

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Configuration

Copy `.env` and set:

```
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/newsfactcheck
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.6-flash
GEMINI_API_KEY=...

# Optional: general web search
WEB_SEARCH_PROVIDER=tavily
WEB_SEARCH_API_KEY=...
WEB_SEARCH_ENDPOINT=https://api.tavily.com/search

# Optional: primary / authoritative source search
PRIMARY_SOURCE_PROVIDER=brave
PRIMARY_SOURCE_API_KEY=...
```

### Health and diagnostics

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/llm
```

`/health/llm` performs a live probe and reports the exact remediation if
reasoning is unavailable, for example when the provider quota is exhausted or
the configured model is retired.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## API

```bash
curl -X POST http://localhost:8000/api/v1/investigations \
  -H "Content-Type: application/json" \
  -d '{"claim": "The city reduced traffic by 20% after the new lane opened."}'

curl http://localhost:8000/api/v1/investigations/1
```

The response includes the overall verdict and confidence, per-subclaim
verification results, every evidence item with its stance, the independence
summary, the completeness assessment, the primary evidence status, and whether
live LLM reasoning was available for that run.

## Tests

```bash
python -m pytest
```

The suite runs fully offline by forcing the deterministic fallbacks, and covers
the core contract: that topical relevance does not become support, that the
model cannot override a detected contradiction, that article count does not
become confidence, that syndicated copies do not become independent evidence,
and that a conclusion is stored separately from the evidence it rests on.

## Current limitations

- Verdicts are research aids, not absolute truth, and are not calibrated.
- Media labels are distribution-level summaries, not truth claims.
- Propositional assessment depends on live LLM reasoning. Without it the system
  reports `llm_available: false` and records documents as non-probative rather
  than guessing.
- The pipeline runs synchronously and is optimised for a local demo and research
  workflow rather than production deployment.
