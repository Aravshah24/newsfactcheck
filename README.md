# NewsFactCheck

## What this project does

NewsFactCheck is a local Phase 1 fact-checking demo that takes a news claim, decomposes it into subclaims, gathers supporting and opposing evidence, checks for primary or authoritative sources, analyzes source independence and completeness, and produces a structured investigation report with a transparent verdict and uncertainty.

It is designed to help people understand the workflow and tradeoffs of evidence-based adjudication without pretending to produce absolute truth.

## Architecture

Claim
→ Claim Analyzer
→ Source Discovery / Opposition / Primary Evidence
→ Evidence Extraction
→ Deduplication / Clustering
→ Completeness
→ Verification
→ Media Analysis
→ Writer

## Agents

- Claim Analyzer: split a claim into atomic, checkable subclaims.
- Source Discovery: gather direct reporting and candidate documents.
- Opposition Agent: searches for contradictory, outdated, or incomplete counter-evidence.
- Primary / Authoritative Source Search: looks for official or institutional sources when relevant.
- Evidence Extraction: converts documents into raw evidence linked to the correct subclaim.
- Completeness Agent: identifies missing context, qualifiers, and omission risks.
- Verification Agent: determines supported / partially supported / disputed / insufficient evidence from the evidence base.
- Media Analysis: summarizes publisher distribution and framing without claiming the claim is true or false.
- Writer: assembles a readable final report using the evidence actually retrieved.

## Why opposition exists

If we only search for reporting that matches the original claim, we may miss the most important reason to doubt it. The opposition pass intentionally searches for disconfirming explanations, timeline disputes, missing qualifications, contradictory numbers, and causal overstatements.

## Why source independence matters

Ten articles from one syndicated report are not ten independent confirmations. Source independence matters because multiple duplicates and republished pieces can inflate confidence even when they are not genuinely independent evidence.

## Completeness

A claim can be factually supported and still incomplete or misleading. Completeness analysis checks for missing comparisons, omitted baselines, missing time periods, broad causal language, and qualifications the audience would need to interpret the claim correctly.

## Media analysis

Media analysis is separate from verification. It summarizes publisher distribution and framing, and it may use publisher-level orientation labels when available. That does not determine factual truth; it only helps explain how coverage is shaping the story.

## Running locally

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Demo mode

```bash
cd backend
$env:DEMO_MODE="true"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The demo mode uses deterministic fixture evidence so the pipeline works even without GDELT or paid APIs.

## Current limitations

- Phase 1 is intentionally simple and understandable.
- It is not production-grade or fully calibrated.
- It does not claim mathematical certainty.
- Media labels are distribution-level summaries, not truth claims.
- The system is optimized for a local demo and research workflow rather than production deployment.

## Sample claims

- The city reduced traffic by 20% after the new lane opened.
- The government announced a 15% tax cut and the policy caused spending to rise.

## Local demo commands

```bash
cd backend
$env:DEMO_MODE="true"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

cd frontend
npm install
npm run dev
```

Then open the frontend and submit a claim.
