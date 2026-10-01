# Architecture overview

## The central distinction

The system keeps three things strictly separate, and conflating them is the main
way a fact-checker goes wrong:

```
RETRIEVED DOCUMENT  !=  EVIDENCE  !=  SUPPORTING EVIDENCE
```

- A **retrieved document** is a URL that a search channel returned. It is a lead,
  not a finding. Being about the same topic proves nothing.
- **evidence** exists only after a document has been compared against the
  *complete proposition* of a subclaim. The comparison is dimension by
  dimension, and the result of that comparison is recorded on the row.
- **supporting evidence** is evidence whose comparison returned `supports` on
  every dimension the claim specifies. Nothing else can become support.

A document that merely shares a subject, a name, or an event type is recorded as
`context` or `neutral`. It never becomes support.

## Proposition dimensions

Every claim and every evidence document is compared along the same generic
dimensions. These are linguistic roles, not domain categories:

| dimension   | question it answers                                    |
| ----------- | ------------------------------------------------------ |
| subject     | who or what is the statement about                      |
| action      | what event, predicate, or relation is asserted          |
| object      | what object, location, target, or complement is involved |
| date_time   | when                                                    |
| quantity    | how much                                                |
| polarity    | is the claim affirmative or does it assert absence       |
| qualifiers  | what scope, exception, or hedge limits the statement    |

A conflict on **any** dimension makes the document contradict the claim. Support
requires a match on **every** dimension the claim specifies. There are no
entity-, event-, or location-specific rules anywhere in the codebase: the
semantics come from the structured decomposition, not from hardcoded vocabularies.

## High-level pipeline

User Claim
  -> Claim Analyzer (atomic subclaims)
  -> Proposition extraction (dimensions per subclaim)
  -> GDELT search
  -> general web search
  -> opposition / counter-evidence search
  -> primary / authoritative source search
  -> deduplication and syndication detection (at ingestion)
  -> Evidence Collector
  -> Evidence Extractor (dimension-by-dimension assessment)
  -> source and story clustering into independence groups
  -> independence analysis
  -> completeness analysis
  -> verification (model proposes, guard rails dispose)
  -> verdict
  -> media coverage analysis
  -> evidence-constrained writer
  -> final report

## Key architectural choices

1. Retrieval channels are independent by design and are not collapsed into a
   single source of truth.
2. GDELT acts as one signal in a broader evidence network rather than the
   canonical fact source.
3. The database stores raw documents, agent interpretations, and verified
   conclusions separately.
4. Deduplication runs at ingestion, so a republished article never reaches
   evidence extraction as a second independent item.
5. Clustering is derived from recorded source relationships, so repeated
   reporting and shared-source dependency are visible.
6. The model proposes; deterministic guard rails dispose. A verdict can never
   claim support the assessed evidence does not carry.
7. Confidence is capped by the number of genuinely independent source groups,
   never by the number of articles retrieved.
8. The final writer is constrained by verified evidence and cannot invent
   unsupported facts.

## Guard rails in verification

The model proposes a verdict. The following deterministic rules then apply to
both the model path and the fallback path, and each one is recorded in
`applied_rules` on the stored conclusion:

1. `no_supporting_evidence` - a supported verdict is refused when nothing entails
   the proposition.
2. `contradicting_evidence_present` - contradicting evidence blocks an
   unqualified supported verdict.
3. `no_probative_evidence` - topical but non-probative documents cannot yield a
   positive verdict.
4. `single_independent_source` - support from one source group is reported as
   partial, not as fully supported.
5. `misleading_by_omission` - completeness can downgrade a verdict but never
   upgrade one.
6. `confidence_capped_by_independence` - confidence is bounded by how many
   independent groups produced the supporting evidence.

## Data model direction

- `documents` - retrieved documents, with publisher, content hash, and source
  type.
- `evidence_items` - agent interpretation of a document against a subclaim,
  carrying `stance`, `assessment_status`, `confidence_score`, and the full
  dimension analysis in metadata.
- `subclaim_conclusions` - verified conclusions, stored separately from the
  evidence they rest on, with the evidence ids they used and the rules applied.
- `source_relationships` - syndication, copying, and citation edges.
- `evidence_clusters` - independence groups derived from those edges.
- `verification_results`, `completeness_results`, `media_analyses`, `reports` -
  stage outputs.

Each record retains provenance and evidence status so the system can explain why
a conclusion was reached.

## Degradation

Live LLM reasoning is optional but always reported. When the provider is
unavailable, the API response and `GET /health/llm` state what failed and what
to fix. The system never fabricates structured output: it either returns a real
comparison or it records the document as non-probative context, because absence
of a model can never manufacture support.

## Execution model

The project intentionally keeps the architecture lightweight and avoids
unnecessary infrastructure. The pipeline runs synchronously so a caller receives
a finished, inspectable result. A long-running asynchronous mode can be layered
on later without changing the response contract.
