from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, Field

from app.config import settings
from app.models import SearchRun, SearchChannel, Subclaim
from app.services.llm import LLMClient


class CounterEvidenceQuerySchema(BaseModel):
    queries: list[str] = Field(default_factory=list)


class OppositionAgent:
    """Search for evidence that would disconfirm a subclaim or reveal a failure mode."""

    def __init__(self, retrievers=None):
        self.retrievers = retrievers or []

    def generate_queries(self, claim_text: str) -> list[str]:
        cleaned = (claim_text or "").strip()
        if not cleaned:
            return []

        try:
            response = LLMClient().generate_structured(
                CounterEvidenceQuerySchema,
                f"Generate up to 5 search queries that would find counter-evidence or omitted context for this claim. Use only the claim text.\n\nCLAIM:\n{cleaned}",
                system_prompt="Return JSON with a 'queries' list of search strings. These must be clear, evidence-seeking queries that look for rebuttals, qualifiers, timeline issues, or omitted context. Use only the supplied claim text."
            )
            values = getattr(response, "queries", None) or getattr(response, "model_dump", lambda: {})().get("queries", [])
            if isinstance(values, list) and values and all(isinstance(item, str) for item in values):
                return [item.strip() for item in values if item and item.strip()][:6]
        except Exception:
            pass

        base = cleaned
        return [
            f"{base} alternative explanation",
            f"{base} disputed timeline",
            f"{base} contradictory evidence",
            f"{base} rebuttal",
            f"{base} correction",
            f"{base} omitted qualification",
        ]

    def search_counter_evidence(self, subclaim: Subclaim) -> list[dict]:
        documents: list[dict] = []
        for query in self.generate_queries(subclaim.text):
            for retriever in self.retrievers:
                try:
                    results = retriever.search(subclaim, query, max_results=5)
                except Exception:
                    continue
                for result in results[:1]:
                    result_payload = result if isinstance(result, dict) else dict(result)
                    if result_payload.get("url"):
                        documents.append(result_payload)
                        break
                if documents:
                    return documents
        return documents
