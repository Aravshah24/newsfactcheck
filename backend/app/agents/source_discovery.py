from __future__ import annotations

import logging
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.config import settings
from app.models import SearchChannel, SearchRun, Subclaim
from app.services.deduplication import DeduplicationService
from app.services.document_normalizer import DocumentNormalizer
from app.services.llm import LLMClient, LLMUnavailableError

logger = logging.getLogger(__name__)

class ClaimQueriesSchema(BaseModel):
    queries: list[str] = Field(default_factory=list)


_QUERY_INSTRUCTION = """Write search queries that would retrieve reporting about a single statement.

Cover a mix of angles without assuming the statement is true or false:
  - the statement itself, in neutral terms
  - official or primary records about the same event
  - independent reporting about the same event
  - the specific figure, date, or location named in the statement

Return JSON with a "queries" list of at most 4 natural search strings, built only from
the supplied statement. Do not add outside facts."""


class SourceDiscoveryAgent:
    """Generate queries and normalise candidate documents from multiple channels.

    Discovery returns documents, not evidence. Deduplication happens here, at
    ingestion, so a syndicated copy never reaches evidence extraction as a
    second independent item.
    """

    def __init__(self, retrievers=None, llm: LLMClient | None = None):
        self.retrievers = retrievers or []
        self.llm = llm or LLMClient()

    @staticmethod
    def _safe_channel_name(retriever: object) -> str:
        channel_name = getattr(retriever, "channel_name", None)
        if isinstance(channel_name, str) and channel_name.strip():
            return channel_name.strip()
        return SearchChannel.OTHER.value

    def generate_queries(self, subclaim: Subclaim) -> list[str]:
        base = (getattr(subclaim, "text", "") or "").strip()
        if not base:
            return []

        try:
            response = self.llm.generate_structured(
                ClaimQueriesSchema,
                f"STATEMENT:\n{base}",
                system_prompt=_QUERY_INSTRUCTION,
            )
            values = getattr(response, "queries", None)
            if isinstance(values, list) and values and all(isinstance(item, str) for item in values):
                queries = [item.strip() for item in values if item and item.strip()]
                if queries:
                    return self._dedupe_queries(queries)[: settings.SEARCH_MAX_QUERIES_PER_SUBCLAIM]
        except LLMUnavailableError as exc:
            logger.info("Query generation fell back to templates: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Query generation failed: %s", exc)

        return self._dedupe_queries(
            [
                base,
                f"{base} official statement",
                f"{base} reported",
                f"{base} primary record",
            ]
        )[: settings.SEARCH_MAX_QUERIES_PER_SUBCLAIM]

    @staticmethod
    def _dedupe_queries(queries: list[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for query in queries:
            collapsed = " ".join(str(query).split())
            if collapsed and collapsed.lower() not in seen:
                unique.append(collapsed)
                seen.add(collapsed.lower())
        return unique

    def discover(self, db, subclaim: Subclaim) -> list:
        documents = []
        max_results = int(settings.SEARCH_MAX_RESULTS_PER_QUERY)

        for query in self.generate_queries(subclaim):
            for retriever in self.retrievers:
                channel_name = self._safe_channel_name(retriever)
                try:
                    results = retriever.search(subclaim, query, max_results=max_results)
                except Exception as exc:  # noqa: BLE001 - isolate channel failures
                    logger.info("Channel %s failed for subclaim %s: %s", channel_name, subclaim.id, exc)
                    self._record_search(db, subclaim, channel_name, query, 0, error=str(exc))
                    continue

                self._record_search(db, subclaim, channel_name, query, len(results or []))
                for result in results or []:
                    payload = dict(result) if not isinstance(result, dict) else result
                    document = DocumentNormalizer.normalize_document(
                        db,
                        {
                            **payload,
                            "publisher": payload.get("publisher") or "Unknown publisher",
                            "domain": payload.get("metadata", {}).get("domain") or payload.get("domain"),
                            "source_type": payload.get("source_type") or "news",
                        },
                        claim_id=subclaim.claim_id,
                        subclaim_id=subclaim.id,
                    )
                    if document not in documents:
                        documents.append(document)

        return DeduplicationService.normalize_and_dedupe(db, documents)

    @staticmethod
    def _record_search(db, subclaim, channel_name: str, query: str, result_count: int, error: str | None = None) -> None:
        try:
            metadata: dict = {"provider": channel_name}
            if error:
                metadata["error"] = error
            # A savepoint keeps a failed bookkeeping insert from discarding the
            # documents collected from earlier retrieval channels.
            with db.begin_nested():
                db.add(
                    SearchRun(
                        claim_id=subclaim.claim_id,
                        subclaim_id=subclaim.id,
                        retrieval_channel=channel_name,
                        query=query,
                        started_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                        result_count=result_count,
                        extra_metadata=metadata,
                    )
                )
        except Exception as exc:  # noqa: BLE001 - bookkeeping must not break retrieval
            logger.info("Could not record search run: %s", exc)
