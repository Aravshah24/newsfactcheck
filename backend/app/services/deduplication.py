from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Document, SourceRelationship, SourceRelationshipType


class DeduplicationService:
    @staticmethod
    def resolve_duplicate_document(session: Session, document: Document) -> Document | None:
        if not document.url:
            return None

        existing = session.query(Document).filter(Document.url == document.url).first()
        if existing and existing.id != document.id:
            return existing

        if document.canonical_url:
            existing = session.query(Document).filter(Document.canonical_url == document.canonical_url).first()
            if existing and existing.id != document.id:
                return existing

        return None

    @staticmethod
    def create_obvious_relationships(session: Session, source: Document, target: Document) -> Document | None:
        if source.id == target.id:
            return None

        relationship_type: SourceRelationshipType | None = None
        if source.url == target.url or source.canonical_url == target.canonical_url:
            relationship_type = SourceRelationshipType.COPIED_FROM
        elif source.content_hash and target.content_hash and source.content_hash == target.content_hash:
            relationship_type = SourceRelationshipType.SYNDICATED_FROM

        if relationship_type is None:
            return None

        existing = (
            session.query(SourceRelationship)
            .filter(
                SourceRelationship.source_document_id == source.id,
                SourceRelationship.target_document_id == target.id,
                SourceRelationship.relationship_type == relationship_type,
            )
            .first()
        )
        if existing:
            return None

        relation = SourceRelationship(
            source_document_id=source.id,
            target_document_id=target.id,
            relationship_type=relationship_type,
            confidence=0.9,
            evidence_justification="Obvious duplicate or republished relationship detected during normalization.",
        )
        session.add(relation)
        session.flush()
        return target

    @staticmethod
    def normalize_and_dedupe(session: Session, documents: list[Document]) -> list[Document]:
        unique: list[Document] = []
        seen: set[int] = set()
        for document in documents:
            duplicate = DeduplicationService.resolve_duplicate_document(session, document)
            if duplicate is not None:
                if duplicate.id not in seen:
                    unique.append(duplicate)
                    seen.add(duplicate.id)
                continue
            if document.id not in seen:
                unique.append(document)
                seen.add(document.id)
        for i, first in enumerate(unique):
            for second in unique[i + 1 :]:
                DeduplicationService.create_obvious_relationships(session, first, second)
        return unique
