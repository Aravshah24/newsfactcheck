# Data layer

This directory defines the storage and artifact conventions for the verification workflow.

## Planned contracts

- raw evidence items retrieved by retrieval channels
- agent interpretations and extracted claims
- evidence provenance metadata and source relationships
- deduplicated clusters for repeated reports
- verification outcomes and final writing artifacts

## Design principles

- Keep raw evidence separated from interpreted evidence.
- Store provenance and verification status alongside every shared artifact.
- Mark repeated coverage or shared-source relationships explicitly.
- Track whether a source is primary, authoritative, or a secondary news publication.
- Preserve the distinction between "not found" and "found and false."
