from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.models import DocumentSourceType, SearchChannel
from app.retrievers.base import Retriever

logger = logging.getLogger(__name__)

# Hosts that conventionally publish the authoritative record for a claim.
_OFFICIAL_HOST_HINTS = (
    ".gov", ".gov.in", ".gov.uk", ".europa.eu", ".un.org", ".int",
    ".mil", ".gc.ca", ".gov.au", ".gouv.fr", ".go.jp", ".nic.in",
)

_INSTITUTIONAL_HINTS = (
    "official", "ministry", "department", "agency", "bureau", "commission",
    "authority", "institute", "statistics", "central bank", "regulator",
    "supreme court", "treasury", "ministry of", "national",
)


class PrimarySourceRetriever(Retriever):
    """Retrieve primary or authoritative records for a subclaim.

    ``SEARCH_FAILED`` is reported distinctly from ``NOT_FOUND`` so a missing
    primary source is never confused with a search that could not run.
    """

    channel_name = SearchChannel.PRIMARY_SOURCE.value

    def __init__(self):
        self.last_status = "NOT_CONFIGURED"

    def is_available(self) -> bool:
        return bool(settings.PRIMARY_SOURCE_PROVIDER and settings.PRIMARY_SOURCE_API_KEY)

    def classify(self, url: str | None, title: str | None, publisher: str | None) -> DocumentSourceType:
        host = (url or "").lower()
        name = (title or "").lower()
        org = (publisher or "").lower()
        if any(hint in host for hint in _OFFICIAL_HOST_HINTS):
            return DocumentSourceType.PRIMARY
        if any(hint in name or hint in org for hint in _INSTITUTIONAL_HINTS):
            return DocumentSourceType.AUTHORITATIVE
        return DocumentSourceType.OTHER

    def search(self, subclaim: Any | None, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        if not self.is_available():
            self.last_status = "NOT_CONFIGURED"
            return []

        endpoint = settings.PRIMARY_SOURCE_ENDPOINT or "https://api.search.brave.com/res/v1/web/search"
        max_results = int(kwargs.get("max_results", settings.PRIMARY_SOURCE_MAX_RESULTS))
        headers = {"Accept": "application/json"}
        if settings.PRIMARY_SOURCE_API_KEY:
            headers["X-Subscription-Token"] = settings.PRIMARY_SOURCE_API_KEY
            headers["Authorization"] = f"Bearer {settings.PRIMARY_SOURCE_API_KEY}"

        try:
            response = httpx.get(
                endpoint,
                params={"q": query, "count": max_results},
                headers=headers,
                timeout=float(kwargs.get("timeout", settings.GDELT_TIMEOUT_SECONDS)),
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            logger.info("Primary source search failed for %r: %s", query, exc)
            self.last_status = "SEARCH_FAILED"
            return []

        results = payload.get("web", {}).get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            results = [item for item in (payload.get("results") or []) if isinstance(item, dict)] if isinstance(payload, dict) else []
        if not results:
            self.last_status = "NOT_FOUND"
            return []

        normalized: list[dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or ""
            title = item.get("title") or "Untitled"
            publisher = item.get("profile") or item.get("publisher") or "Official source"
            normalized.append(
                {
                    "title": title,
                    "url": url,
                    "publisher": publisher,
                    "publication_date": item.get("age") or item.get("page_age"),
                    "content": item.get("description") or "",
                    "retrieval_channel": self.channel_name,
                    "source_type": self.classify(url, title, publisher).value,
                    "query": query,
                    "metadata": {"provider": settings.PRIMARY_SOURCE_PROVIDER, "is_primary_channel": True},
                }
            )

        self.last_status = "FOUND" if normalized else "NOT_FOUND"
        return normalized
