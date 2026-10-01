from __future__ import annotations

from collections import defaultdict

from app.models import Claim, EvidenceCluster


class EvidenceClusteringService:
    """Group evidence that descends from the same underlying reporting.

    Clusters are built from the independence groups computed by
    :class:`~app.services.independence.IndependenceAnalyzer`, so a syndicated or
    republished article lands in the same cluster as its original instead of
    being counted again as a separate confirmation.
    """

    def cluster_from_independence(
        self, session, claim: Claim, independence_summary, evidence_items: list | None = None
    ) -> list[EvidenceCluster]:
        # Accepts either an IndependenceSummary instance or its dict form.
        if isinstance(independence_summary, dict):
            groups = list(independence_summary.get("groups") or [])
            group_for_evidence = dict(independence_summary.get("group_for_evidence") or {})
        else:
            groups = list(getattr(independence_summary, "groups", None) or [])
            group_for_evidence = dict(getattr(independence_summary, "group_for_evidence", None) or {})

        items_by_id = {getattr(item, "id", None) or id(item): item for item in (evidence_items or [])}

        clustered_evidence_ids: set[int] = set()
        created: list[EvidenceCluster] = []
        for group in groups:
            members = [
                items_by_id[evidence_id]
                for evidence_id in group_for_evidence
                if evidence_id in items_by_id
            ]
            if not members:
                continue
            cluster = EvidenceCluster(
                claim_id=claim.id,
                label=f"independence-group-{group['group_id']}",
                description=(
                    f"Documents from {group['document_count']} source(s): "
                    f"{', '.join(group['publishers'][:5])}."
                ),
                clustering_method="source_relationship_components",
                similarity_score=1.0,
            )
            session.add(cluster)
            session.flush()
            cluster.evidence_items = members
            clustered_evidence_ids.update(getattr(item, "id", None) or id(item) for item in members)
            created.append(cluster)

        for evidence_id, item in items_by_id.items():
            if evidence_id in clustered_evidence_ids or getattr(item, "id", None) is None:
                continue
            cluster = EvidenceCluster(
                claim_id=claim.id,
                label=f"unclustered-{getattr(item, 'id', None)}",
                description="Evidence with no resolved document grouping.",
                clustering_method="unclustered",
                similarity_score=None,
            )
            session.add(cluster)
            session.flush()
            cluster.evidence_items = [item]
            created.append(cluster)

        return created

    def cluster_by_document_hash(self, session, claim: Claim) -> list[EvidenceCluster]:
        """Legacy grouping by exact content hash, retained for direct callers."""
        grouped: dict[str, list] = defaultdict(list)
        for evidence in claim.evidence_items:
            if evidence.document is None:
                continue
            key = evidence.document.content_hash or evidence.document.url or "unclustered"
            grouped[key].append(evidence)

        created: list[EvidenceCluster] = []
        for key, items in grouped.items():
            cluster = EvidenceCluster(
                claim_id=claim.id,
                label=f"cluster-{key[:8]}",
                description="Evidence grouped by exact document content hash.",
                clustering_method="document_hash",
                similarity_score=1.0,
            )
            session.add(cluster)
            session.flush()
            cluster.evidence_items = items
            created.append(cluster)
        return created
