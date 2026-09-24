from __future__ import annotations

from collections import defaultdict

from app.models import Claim, EvidenceCluster


class EvidenceClusteringService:
    """Group evidence by heuristically similar documents without claiming independence."""

    def cluster_by_document_hash(self, session, claim: Claim) -> list[EvidenceCluster]:
        grouped: dict[str, list] = defaultdict(list)
        for evidence in claim.evidence_items:
            if evidence.document is None:
                continue
            key = evidence.document.content_hash or evidence.document.url or "unclustered"
            grouped[key].append(evidence)

        created: list[EvidenceCluster] = []
        for key, items in grouped.items():
            if len(items) < 2:
                continue
            cluster = EvidenceCluster(
                claim_id=claim.id,
                label=f"cluster-{key[:8]}",
                description="Evidence grouped by document similarity for downstream analysis.",
                clustering_method="document_hash",
                similarity_score=0.82,
            )
            session.add(cluster)
            session.flush()
            cluster.evidence_items = items
            created.append(cluster)
        return created
