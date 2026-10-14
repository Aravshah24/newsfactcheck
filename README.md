# FactTrace — Evidence-Backed Claim Investigation

> Verdicts are research aids, not ground truth. FactTrace is designed to make the reasoning behind a verdict transparent and auditable, not to replace human judgment.

---

## What problem does this solve?

Most automated fact-checkers conflate three things that are not the same:

```
RETRIEVED DOCUMENT  ≠  EVIDENCE  ≠  SUPPORTING EVIDENCE
```

A document being *about* the same topic as a claim does not mean it supports the claim. FactTrace addresses this by decomposing a claim into atomic subclaims and assessing each retrieved document against the *complete proposition* of the subclaim — dimension by dimension: subject, action, object/location, date, quantity, polarity, and qualifiers. A conflict on any single dimension is a contradiction. Missing coverage of a specified dimension is context, not support. Support requires a match on every specified dimension.

This project also integrates a **media lean analysis layer** — mapping retrieved outlets to independently rated Left/Center/Right positions from AllSides, Media Bias/Fact Check, and Ad Fontes Media (as of a recorded snapshot) — so the reader can see not just *what* the evidence says, but *who* is saying it and what perspectives are underrepresented.

---

## Architecture

```
Claim
  → Claim Analyzer            (atomic subclaims)
  → Proposition Extractor     (dimensions per subclaim)
  → Source Discovery          (multi-channel retrieval: GDELT + Tavily web search)
  → Opposition Agent          (actively searches for contradictions, not just confirming sources)
  → Primary Source Retriever  (domain-restricted: courts, statistics bodies, official records)
  → Evidence Extractor        (dimension-by-dimension stance assessment per document)
  → Independence Grouper      (deduplication and syndication detection)
  → Completeness Agent        (flags missing context, omitted baselines, causal overreach)
  → Verification Agent        (verdict subject to deterministic guard rails)
  → Media Lean Analyzer       (maps outlets to L/C/R/Unknown, computes distribution)
  → Writer                    (renders report; cannot alter a computed verdict)
```

See [`docs/architecture.md`](docs/architecture.md) for the full design rationale, dimension model, and guard rail specification.

---

## Agents

### Claim Analyzer
Splits the input into atomic, independently checkable subclaims. A compound claim ("Country X reduced emissions by 30% after Policy Y") becomes two subclaims: one about the reduction figure, one about the causal link to the policy.

### Proposition Extractor
Decomposes each subclaim into comparable dimensions using LLM-based linguistic analysis. No domain- or entity-specific rules — this is general proposition decomposition applied uniformly.

### Source Discovery
Generates search queries and normalises candidate documents across independent retrieval channels (GDELT, Tavily web search). Channels run concurrently with a configurable worker pool.

**Known limitation:** GDELT and Tavily return article metadata and snippets, not full article text. Paywalled or blocked pages fall back to snippets silently; this is logged but does not surface as an error, to avoid false negatives.

### Opposition Agent
A hard-mandated adversary pass. Rather than only searching for sources that confirm the claim, the Opposition Agent generates disconfirming search angles — corrections, disputed figures, narrower scopes, official records that disagree — and runs them as a separate retrieval pass. Its results are documents, not verdicts; they go through the same propositional assessment as everything else.

**Why this matters:** searching only for confirming coverage can miss the most important reason to doubt a claim.

### Primary Source Retriever
Runs a domain-restricted search against official domains (statistics bodies, court filing registries, government records). Fetches full page text for shortlisted results where accessible. Reports `FOUND`, `NOT_FOUND`, `SEARCH_FAILED`, or `NOT_CONFIGURED` distinctly — never conflates absence of a result with a negative finding. Reuses Tavily credentials; no separate key required.

### Evidence Extractor
Compares each document against the complete proposition of its subclaim and records a stance (`supports` / `contradicts` / `context` / `neutral` / `unknown`) with per-dimension analysis. Topical relevance alone never yields `supports`.

**Implementation note:** dimension-level assessment is performed by the LLM (Gemini). The system does not use a symbolic reasoner or rule-based NLP pipeline for this step. The guard rails described below exist specifically because LLM assessment can be unreliable.

### Independence Grouper
Groups documents by source relationships, shared content hashes, and shared publishers. Confidence is capped by the number of independent groups producing supporting evidence — not by total article count. Ten articles from one syndicated wire report are not ten independent confirmations.

### Completeness Agent
A claim can be factually supported and still be misleading. Completeness analysis checks for: missing comparisons, omitted baselines, missing time periods, broad causal language without a stated mechanism, and qualifiers the reader needs to interpret the claim correctly. Falls back to structural regex checks when the LLM is unavailable.

### Verification Agent
Determines verdict subject to deterministic guard rails:

- A detected contradiction cannot be overridden by the LLM
- Article count is not treated as confidence
- Syndicated copies do not become independent evidence
- Support from only secondary/opinion sources is capped at partial
- Conflicting official records force a disputed verdict
- Confidence is capped by role-weighted independence
- Completeness can downgrade but never upgrade a verdict
- A conclusion is stored separately from the evidence it rests on

**Verdict labels:**

| Label | Meaning |
|---|---|
| `supported` | Every specified dimension of every subclaim matched across at least two independent source groups |
| `partially_supported` | Some subclaims supported; others have insufficient or contradicted evidence |
| `disputed` | At least one dimension has confirmed contradictory evidence from an independent source |
| `misleading_or_incomplete` | Claim is supported but omits context needed to interpret it correctly |
| `unverifiable` | Evidence is insufficient to reach a determination; claim may be unverifiable in principle |
| `insufficient_evidence` | Retrieval returned relevant documents but none assessed as supporting or contradicting |

Verdicts are never `true` or `false`. These labels reflect the state of retrieved evidence, not ground truth.

### Media Lean Analyzer
Maps every retrieved outlet to an independently sourced bias/factuality rating (AllSides, Media Bias/Fact Check, Ad Fontes Media — as of a recorded snapshot). Computes Left/Center/Right/Unknown distribution across retrieved sources.

**Important:** lean analysis is entirely separate from verdict computation. Publisher orientation is a distribution-level description, not evidence for or against the claim. A claim covered only by left-leaning outlets is not thereby false; a claim covered across the spectrum is not thereby true. Outlets not in the rating table fall into `unknown`.

### Writer
Renders the final report using only the evidence actually retrieved and assessed. The Writer receives the computed verdict as a read-only input — it cannot propose, revise, or soften it. Its only responsibility is presentation.

---

## What this system does not do

- It does not calibrate confidence scores against a ground-truth labelled dataset
- It does not compute polarization metrics or narrative divergence (media analysis is distribution-only)
- It does not access paywalled content
- It does not use symbolic or rule-based proposition extraction — LLM assessment is the mechanism, and LLMs can be wrong
- It is not designed for production throughput — the pipeline runs synchronously and is optimised for local research use
- Bias ratings are from a fixed snapshot; outlet ratings can change and small or international outlets often fall into `unknown`

---

## Requirements

- **Docker Desktop** (recommended), or natively: Python 3.11+, Node.js 20+, PostgreSQL 16
- **Gemini API key** (required — without it the system reports `llm_available: false` and records all documents as non-probative rather than guessing)
- **Tavily API key** (optional — without it, retrieval falls back to GDELT only)

---

## Quick start (Docker)

```bash
git clone <repository-url>
cd newsfactcheck
cp backend/.env.example backend/.env
# Open backend/.env and set GEMINI_API_KEY
docker compose up --build
```

- Frontend: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs

Database migrations run automatically on first start. Stop with Ctrl+C; `docker compose down -v` also removes the database volume.

---

## Running natively

```bash
# 1. Start the database
docker compose up -d db

# 2. Backend
cd backend
cp .env.example .env          # set DATABASE_URL and GEMINI_API_KEY
pip install -r requirements.txt
alembic upgrade head
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

---

## Configuration

All settings in `backend/.env`, copied from `backend/.env.example`. Only `GEMINI_API_KEY` is required; every other value has a working default.

```env
GEMINI_API_KEY=...                  # required

WEB_SEARCH_PROVIDER=tavily
WEB_SEARCH_API_KEY=...              # optional; GDELT-only retrieval without it

POSTGRES_DB=newsfactcheck
POSTGRES_USER=newsfactcheck
POSTGRES_PASSWORD=change_me
DATABASE_URL=postgresql+psycopg://newsfactcheck:change_me@localhost:5432/newsfactcheck

LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.1-flash-lite
LLM_FALLBACK_MODELS=gemini-3.1-flash-lite,gemini-3.5-flash-lite
LLM_TIMEOUT_SECONDS=60
LLM_MAX_ATTEMPTS=3
LLM_RETRY_BACKOFF_SECONDS=1.5

RETRIEVAL_MAX_WORKERS=4
RATE_LIMIT_PER_MINUTE=10
DEMO_MODE=false
FASTAPI_ENV=development
ALLOWED_ORIGINS=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

See `backend/.env.example` for the full reference including GDELT parameters, evidence/search/opposition tuning knobs, and all runtime flags.

---

## API

```bash
# Submit a claim for investigation
curl -X POST http://localhost:8000/api/v1/investigations \
  -H "Content-Type: application/json" \
  -d '{"claim": "The city reduced traffic by 20% after the new lane opened."}'

# List stored investigations (newest first)
curl http://localhost:8000/api/v1/investigations

# Load one investigation
curl http://localhost:8000/api/v1/investigations/1

# Delete an investigation and all its records
curl -X DELETE http://localhost:8000/api/v1/investigations/1
```

The response includes: overall verdict and confidence, per-subclaim results, every evidence item with stance and dimension analysis, independence summary, completeness assessment, media lean distribution, primary evidence status, and LLM availability flag.

---

## Health and diagnostics

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/llm    # live probe; reports exact remediation if unavailable
curl http://localhost:8000/api/v1/health
```

---

## Tests

```bash
python -m pytest
```

The suite runs fully offline using deterministic fallbacks. Core contracts tested:
- Topical relevance does not become support
- A detected contradiction cannot be overridden by the model
- Article count does not become confidence
- Syndicated copies do not become independent evidence
- A conclusion is stored separately from the evidence it rests on

---

## Troubleshooting

**Port 5432 already in use:** set `POSTGRES_PORT=5433` in `backend/.env`; if running the backend natively, update `DATABASE_URL` to match.

**Changed `POSTGRES_PASSWORD` after first start:** the original password is baked into the `postgres_data` volume. Run `docker compose down -v` to wipe it, then `docker compose up --build`.

**LLM unavailable:** call `/health/llm` — it reports whether the key is missing, quota is exhausted, or the model name is retired. The system does not guess verdicts when the LLM is unavailable; documents are marked `non-probative` and the investigation is stored for re-running.

---

## Known limitations

- Verdict confidence is not calibrated against a labelled ground-truth dataset
- Proposition extraction and evidence assessment are LLM-delegated — the deterministic guard rails exist precisely because this step can fail silently
- Retrieval is snippet-level for most sources; full-text fetch is best-effort and paywalled pages are not accessible
- The pipeline is synchronous — not suitable for high-throughput or concurrent multi-user use
- Bias ratings come from a fixed snapshot; outlets not in the rating table fall into `unknown`
- Media analysis reports lean distribution only; it does not measure polarization or narrative divergence
- `DEMO_MODE=true` hides provider and model names from reports and diagnostics