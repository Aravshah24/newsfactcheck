from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models import Document, EvidenceItem, SourceRelationship, SourceRelationshipType

# Relationship types that mean "this document did not independently observe the event".
DEPENDENCY_TYPES = {
    SourceRelationshipType.SYNDICATED_FROM.value,
    SourceRelationshipType.COPIED_FROM.value,
    SourceRelationshipType.TRANSLATES.value,
}

_INDEPENDENT_SYSTEM_MARKERS = ("official", "government", "ministry", "department", "agency", "bureau", "court")


@dataclass
class IndependenceSummary:
    documents_found: int = 0
    distinct_publishers: int = 0
    evidence_items: int = 0
    independent_groups: int = 0
    duplicate_documents: int = 0
    dependency_edges: int = 0
    groups: list[dict] = field(default_factory=list)
    group_for_evidence: dict[int, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "documents_found": self.documents_found,
            "distinct_publishers": self.distinct_publishers,
            "evidence_items": self.evidence_items,
            "evidence_clusters": self.independent_groups,
            "independent_groups": self.independent_groups,
            "estimated_independent_sources": max(1, self.independent_groups),
            "duplicate_derived_documents": self.duplicate_documents,
            "dependency_edges": self.dependency_edges,
            "groups": self.groups,
        }


class _UnionFind:
    def __init__(self):
        self._parent: dict[int, int] = {}

    def add(self, item: int) -> None:
        self._parent.setdefault(item, item)

    def find(self, item: int) -> int:
        self.add(item)
        root = item
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[item] != root:
            self._parent[item], item = root, self._parent[item]
        return root

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self._parent[right_root] = left_root


class IndependenceAnalyzer:
    """Compute how many genuinely independent observation groups back the evidence.

    Independence is derived from recorded source relationships, shared publishers,
    and shared content hashes. Articles that copy, syndicate, or translate one
    another collapse into a single group, so republishing cannot inflate
    confidence.
    """

    def analyze(
        self,
        session: Session,
        claim,
        documents: list[Document] | None = None,
        evidence_items: list[EvidenceItem] | None = None,
    ) -> IndependenceSummary:
        documents = list(documents or [])
        evidence_items = list(evidence_items or [])
        summary = IndependenceSummary(
            documents_found=len(documents),
            evidence_items=len(evidence_items),
        )

        publishers = {
            document.id: getattr(getattr(document, "publisher", None), "name", None) or "Unknown publisher"
            for document in documents
        }
        summary.distinct_publishers = len(set(publishers.values()))

        union = _UnionFind()
        for document in documents:
            union.add(document.id)

        # 1. Explicit dependency edges recorded during deduplication.
        document_ids = {document.id for document in documents}
        edges = (
            session.query(SourceRelationship)
            .filter(SourceRelationship.source_document_id.in_(document_ids))
            .all()
            if document_ids
            else []
        )
        for relationship in edges:
            value = str(getattr(relationship.relationship_type, "value", relationship.relationship_type))
            if value in DEPENDENCY_TYPES:
                if relationship.target_document_id in document_ids:
                    union.union(relationship.source_document_id, relationship.target_document_id)
                summary.dependency_edges += 1

        # 2. Identical content hash: the same wire copy under different URLs.
        by_hash: dict[str, list[int]] = defaultdict(list)
        for document in documents:
            if document.content_hash:
                by_hash[document.content_hash].append(document.id)
        for document_ids_with_hash in by_hash.values():
            for other in document_ids_with_hash[1:]:
                union.union(document_ids_with_hash[0], other)
                summary.duplicate_documents += 1

        # 3. Same publisher: one outlet reporting many times is still one observer.
        by_publisher: dict[str, list[int]] = defaultdict(list)
        for document in documents:
            by_publisher[publishers.get(document.id, "Unknown publisher")].append(document.id)
        for document_ids_for_publisher in by_publisher.values():
            if len(document_ids_for_publisher) > 1:
                for other in document_ids_for_publisher[1:]:
                    union.union(document_ids_for_publisher[0], other)

        # Collapse the components.
        components: dict[int, list[Document]] = defaultdict(list)
        for document in documents:
            components[union.find(document.id)].append(document)

        groups: list[dict] = []
        for index, (_, members) in enumerate(sorted(components.items(), key=lambda pair: -len(pair[1])), start=1):
            member_ids = {document.id for document in members}
            publisher_names = sorted({publishers.get(document.id, "Unknown publisher") for document in members})
            group = {
                "group_id": index,
                "document_ids": sorted(member_ids),
                "document_count": len(members),
                "publishers": publisher_names,
                "is_primary_or_official": any(
                    any(marker in name.lower() for marker in _INDEPENDENT_SYSTEM_MARKERS)
                    for name in publisher_names
                ),
            }
            groups.append(group)
            for document_id in member_ids:
                for evidence in evidence_items:
                    if evidence.document_id == document_id:
                        summary.group_for_evidence[evidence.id if evidence.id else id(evidence)] = index

        summary.groups = groups
        summary.independent_groups = len(groups)
        return summary
