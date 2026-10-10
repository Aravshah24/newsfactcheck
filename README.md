# NewsFactCheck

**Product name:** FactTrace — Evidence-backed claim investigation

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
- **Primary Source Retriever** - runs a domain-restricted search (statistics
  bodies, courts, filing registries) against official domains, fetches the full
  page text of the records it keeps, and reports `FOUND`, `NOT_FOUND`,
  `SEARCH_FAILED`, or `NOT_CONFIGURED` distinctly. No separate API key: it reuses
  the web-search (Tavily) credentials.
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

Lean labels come from independent reviewers (AllSides, Media Bias/Fact Check,
Ad Fontes Media) as of a recorded snapshot and are surfaced in the UI with a
left / center / right / unknown split. Outlets without a rating fall into the
`unknown` bucket; leans are never guessed.

## Requirements

- **Docker Desktop** (recommended path), or natively: Python 3.11+, Node.js 20+, and PostgreSQL 16.
- A **Gemini API key** (required for live propositional reasoning; the system
  reports clearly when it is unavailable and never fabricates results).

## Quick start (Docker)

The fastest way to run the whole stack. You only need Docker Desktop and a
Gemini API key.

```bash
git clone <repository-url>
cd newsfactcheck
cp backend/.env.example backend/.env
```

Open `.env` and set at least your key:

```
GEMINI_API_KEY=your-key-here
```

Then start everything:

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs

Database migrations run automatically when the backend container starts. Stop
with Ctrl+C; run `docker compose down` to stop and `docker compose down -v` to
also delete the stored database volume.

## Configuration

All settings live in one file, copied from `backend/.env.example`. Only the Gemini key
is required. Every other value has a working default. The block below shows the
core settings; see `backend/.env.example` for the complete reference including
runtime flags (`FASTAPI_ENV`, `DEMO_MODE`, `NEXT_PUBLIC_API_URL`, `ALLOWED_ORIGINS`,
`RATE_LIMIT_PER_MINUTE`), full GDELT parameters, and all evidence/search/opposition
tuning knobs (`EVIDENCE_*`, `SEARCH_*`, `OPPOSITION_*`).

```
GEMINI_API_KEY=...                 # required

# Database. POSTGRES_* configure the Docker stack; DATABASE_URL is used for
# native runs (the compose backend always targets the db service).
POSTGRES_DB=newsfactcheck
POSTGRES_USER=newsfactcheck
POSTGRES_PASSWORD=change_me
DATABASE_URL=postgresql+psycopg://newsfactcheck:change_me@localhost:5432/newsfactcheck

# Model (Gemini only).
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.8-flash
LLM_FALLBACK_MODELS=gemini-3.8-flash,gemini-flash-latest,gemini-2.5-flash
LLM_TIMEOUT_SECONDS=60
LLM_MAX_ATTEMPTS=3
LLM_RETRY_BACKOFF_SECONDS=1.5

# Optional: general web search.
WEB_SEARCH_PROVIDER=tavily
WEB_SEARCH_API_KEY=...
WEB_SEARCH_ENDPOINT=https://api.tavily.com/search

# Primary / authoritative source search. Shares the Tavily key above and
# restricts results to official domains; the *_PRIMARY_SOURCE_* values only
# override the endpoint/key when dedicated credentials exist.
PRIMARY_SOURCE_API_KEY=
PRIMARY_SOURCE_ENDPOINT=
PRIMARY_SOURCE_MAX_RESULTS=5
# Full-page fetch for the primary shortlist (best-effort).
PRIMARY_FETCH_ENABLED=true
PRIMARY_FETCH_TIMEOUT_SECONDS=15
PRIMARY_FETCH_MAX_CHARS=8000
PRIMARY_FETCH_INTERVAL_SECONDS=1

# GDELT retrieval (always available, no key). Shared IP is rate-limited to ~1
# req/5s; when it answers 429 repeatedly the circuit breaker opens and GDELT
# is skipped for the cooldown instead of stalling every query.
GDELT_API_URL=https://api.gdeltproject.org/api/v2/doc/doc
GDELT_MAX_RESULTS=10
GDELT_TIMESPAN_DAYS=7
GDELT_LANGUAGE=en
GDELT_TIMEOUT_SECONDS=10
GDELT_MIN_INTERVAL_SECONDS=5
GDELT_MAX_RETRIES=2
GDELT_BREAKER_THRESHOLD=3
GDELT_BREAKER_COOLDOWN_SECONDS=60

# Retrieval channels and queries run concurrently. Database writes stay
# sequential; only the network calls are parallel.
RETRIEVAL_MAX_WORKERS=4
```

Never commit `.env`; only `backend/.env.example` is tracked.

### Health and diagnostics

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/llm
curl http://localhost:8000/api/v1/health
```

`/health` returns basic service status. `/health/llm` performs a live probe and reports the exact remediation if reasoning is unavailable, for example when the provider quota is exhausted or the configured model is retired. `/api/v1/health` is the versioned API health endpoint (used by the frontend for connection checks).

## Running natively (without Docker)

Use this if you prefer running the app directly. You need PostgreSQL 16, Python
3.11+, and Node.js 20+ installed, plus the env file at `backend/.env`.

```bash
# 1. Start a database (the compose db service is enough).
docker compose up -d db

# 2. Backend
cd backend
cp .env.example .env          # edit DATABASE_URL + GEMINI_API_KEY
pip install -r requirements.txt
alembic upgrade head
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

## Troubleshooting

- **`port is already allocated` for 5432**: another PostgreSQL is running. Set
  `POSTGRES_PORT=5433` in `backend/.env` and restart; if you run the backend natively,
  point `DATABASE_URL` at the same port.
- **Changed `POSTGRES_PASSWORD` after the first start**: the original password
  is stored in the `postgres_data` volume. Run `docker compose down -v` to
  recreate the volume, then `docker compose up --build`.
- **Reasoning unavailable**: call `/health/llm`; it reports whether the key is
  missing, the quota is exhausted, or the model name is retired.

## API

```bash
curl -X POST http://localhost:8000/api/v1/investigations \
  -H "Content-Type: application/json" \
  -d '{"claim": "The city reduced traffic by 20% after the new lane opened."}'

# List stored investigations (newest first)
curl http://localhost:8000/api/v1/investigations

# Load one investigation
curl http://localhost:8000/api/v1/investigations/1

# Delete one investigation and all of its records
curl -X DELETE http://localhost:8000/api/v1/investigations/1
```

The response includes the overall verdict and confidence, per-subclaim
verification results, every evidence item with its stance, the independence
summary, the completeness assessment, the primary evidence status, and whether
live LLM reasoning was available for that run.

The investigation endpoint is rate-limited per client IP
(`RATE_LIMIT_PER_MINUTE`, default 10) and only the origins in `ALLOWED_ORIGINS`
may call the API. Set `DEMO_MODE=true` to hide provider and model names from the
report and diagnostics.

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
- Primary-source page fetching is best-effort: a page that cannot be fetched
  (paywall, block, timeout) leaves the search snippet in place.
- Propositional assessment depends on live LLM reasoning. Without it the system
  reports `llm_available: false` and records documents as non-probative rather
  than guessing.
- The pipeline runs synchronously and is optimised for a local demo and research
  workflow rather than production deployment.
