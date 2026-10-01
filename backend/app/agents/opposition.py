from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel, Field

from app.config import settings
from app.models import SearchChannel, SearchRun
from app.services.llm import LLMClient, LLMUnavailableError

logger = logging.getLogger(__name__)


class CounterEvidenceQuerySchema(BaseModel):
    queries: list[str] = Field(default_factory=list)


_QUERY_INSTRUCTION = """Write search queries that would surface material that DISCONFIRMS a claim.

Aim for:
  - a documented correction, retraction, or denial
  - a different figure, date, or location for the same event
  - a narrower scope or an important exception the claim omits
  - an official or primary record that disagrees
  - an alternative explanation of the same event

Write each query as natural search terms, not as a question. Do not assert that the
claim is false; you are looking for material either way. Return JSON with a "queries"
list of at most 5 strings, using only the supplied claim text."""


class OppositionAgent:
    """Search for evidence that would disconfirm a subclaim or reveal a failure mode.

    The pass runs alongside supporting retrieval. Its results are documents, not
    verdicts: every returned document goes through the same propositional
    assessment as any other, so a counter-search cannot manufacture a dispute and
    a supporting search cannot manufacture support.
    """

    def __init__(self, retrievers=None, llm: LLMClient | None = None):
        self.retrievers = retrievers or []
        self.llm = llm or LLMClient()

    def generate_queries(self, claim_text: str) -> list[str]:
        cleaned = (claim_text or "").strip()
        if not cleaned:
            return []

        try:
            response = self.llm.generate_structured(
                CounterEvidenceQuerySchema,
                f"CLAIM:\n{cleaned}",
                system_prompt=_QUERY_INSTRUCTION,
            )
            values = response.queries
            if isinstance(values, list) and values and all(isinstance(item, str) for item in values):
                queries = [item.strip() for item in values if item and item.strip()][:5]
                if queries:
                    return queries
        except LLMUnavailableError as exc:
            logger.info("Opposition query generation fell back to templates: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Opposition query generation failed: %s", exc)

        return [
            f"{cleaned} correction",
            f"{cleaned} denied",
            f"{cleaned} disputed",
            f"{cleaned} inaccurate",
            f"{cleaned} official record",
        ]

    def search_counter_evidence(self, subclaim, db=None) -> list[dict]:
        """Return candidate counter-documents for a subclaim across all channels."""
        max_results = int(settings.OPPOSITION_MAX_RESULTS)
        documents: list[dict] = []
        seen_urls: set[str] = set()

        for query in self.generate_queries(getattr(subclaim, "text", str(subclaim))):
            for retriever in self.retrievers:
                try:
                    results = retriever.search(subclaim, query, max_results=max_results)
                except Exception as exc:  # noqa: BLE001 - one channel must not stop the pass
                    logger.info("Opposition channel %s failed: %s", getattr(retriever, "channel_name", retriever), exc)
                    if db is not None:
                        self._record_search(db, subclaim, retriever, query, 0, error=str(exc))
                    continue

                if db is not None:
                    self._record_search(db, subclaim, retriever, query, len(results))

                for result in results:
                    payload = result if isinstance(result, dict) else dict(result)
                    url = payload.get("url")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    payload.setdefault("retrieval_channel", getattr(retriever, "channel_name", SearchChannel.OTHER.value))
                    payload["search_intent"] = "opposition"
                    documents.append(payload)
                    if len(documents) >= max_results:
                        return documents
        return documents

    @staticmethod
    def _record_search(db, subclaim, retriever, query: str, result_count: int, error: str | None = None) -> None:
        try:
            metadata: dict = {"provider": getattr(retriever, "channel_name", SearchChannel.OTHER.value)}
            if error:
                metadata["error"] = error
            # A savepoint keeps a failed bookkeeping insert from discarding the
            # documents already collected from earlier retrieval channels.
            with db.begin_nested():
                db.add(
                    SearchRun(
                        claim_id=getattr(subclaim, "claim_id", None),
                        subclaim_id=getattr(subclaim, "id", None),
                        retrieval_channel=getattr(retriever, "channel_name", SearchChannel.OTHER.value),
                        query=query,
                        started_at=datetime.now(),
                        completed_at=datetime.now(),
                        result_count=result_count,
                        extra_metadata=metadata,
                    )
                )
        except Exception as exc:  # noqa: BLE001 - bookkeeping must not break retrieval
            logger.info("Could not record opposition search run: %s", exc)
