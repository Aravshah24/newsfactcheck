# Data layer

This directory defines the storage and artifact conventions for the verification workflow.

## Implemented contracts

- Raw evidence items retrieved by retrieval channels → `backend/app/models/document.py` (`Document`)
- Agent interpretations and extracted claims → `backend/app/models/evidence.py` (`EvidenceItem`, `EvidenceCategory`, `EvidenceStance`, `EvidenceAssessmentStatus`)
- Evidence provenance metadata and source relationships → `backend/app/models/source_relationship.py` (`SourceRelationship`, `SourceRelationshipType`)
- Deduplicated clusters for repeated reports → `backend/app/models/evidence_cluster.py` (`EvidenceCluster`)
- Verification outcomes and final writing artifacts → `backend/app/models/verification.py`, `backend/app/models/report.py`
- Publisher lean table (AllSides/MBFC/Ad Fontes snapshot + `unknown` bucket) → `backend/app/data/outlet_lean.py`

## Design principles

- Keep raw evidence separated from interpreted evidence.
- Store provenance and verification status alongside every shared artifact.
- Mark repeated coverage or shared-source relationships explicitly.
- Track whether a source is primary, authoritative, or a secondary news publication.
- Preserve the distinction between "not found" and "found and false."
