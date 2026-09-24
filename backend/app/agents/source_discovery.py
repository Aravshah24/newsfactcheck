from __future__ import annotations

from datetime import datetime

from app.db.session import SessionLocal
from app.models import SearchChannel, SearchRun, Subclaim
from app.services.document_normalizer import DocumentNormalizer


class SourceDiscoveryAgent:
    """Generate queries and normalize candidate documents from multiple retrieval channels."""

    @staticmethod
    def _safe_channel_name(retriever: object) -> str:
        channel_name = getattr(retriever, "channel_name", None)
        if isinstance(channel_name, str) and channel_name.strip():
            return channel_name.strip()
        return SearchChannel.OTHER.value

    def __init__(self, retrievers=None):
        self.retrievers = retrievers or []

    def generate_queries(self, subclaim: Subclaim) -> list[str]:
        base = subclaim.text.strip()
        if not base:
            return []
        queries = [base, f"{base} official statement", f"{base} reported by", f"{base} source"]
        uniq = []
        seen = set()
        for query in queries:
            q = " ".join(query.split())
            if q and q.lower() not in seen:
                uniq.append(q)
                seen.add(q.lower())
        return uniq[:4]

    def discover(self, db, subclaim: Subclaim) -> list:
        documents = []
        for query in self.generate_queries(subclaim):
            for retriever in self.retrievers:
                channel_name = self._safe_channel_name(retriever)
                try:
                    results = retriever.search(subclaim, query, max_results=5)
                except Exception as exc:
                    search_run = SearchRun(
                        claim_id=subclaim.claim_id,
                        subclaim_id=subclaim.id,
                        retrieval_channel=channel_name,
                        query=query,
                        started_at=datetime.utcnow(),
                        completed_at=datetime.utcnow(),
                        result_count=0,
                        extra_metadata={"provider": channel_name, "error": str(exc)},
                    )
                    db.add(search_run)
                    db.flush()
                    continue
                if not results:
                    continue

                search_run = SearchRun(
                    claim_id=subclaim.claim_id,
                    subclaim_id=subclaim.id,
                    retrieval_channel=channel_name,
                    query=query,
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow(),
                    result_count=len(results),
                    extra_metadata={"provider": channel_name},
                )
                db.add(search_run)
                db.flush()

                for result in results:
                    payload = dict(result)
                    if isinstance(result, dict):
                        payload = result
                    document = DocumentNormalizer.normalize_document(
                        db,
                        {
                            **payload,
                            "publisher": payload.get("publisher") or "Unknown publisher",
                            "domain": payload.get("metadata", {}).get("domain") or payload.get("domain"),
                            "source_type": "news",
                        },
                        claim_id=subclaim.claim_id,
                        subclaim_id=subclaim.id,
                    )
                    documents.append(document)
        return documents
