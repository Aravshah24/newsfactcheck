from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.models import DocumentSourceType, SearchChannel
from app.retrievers.base import Retriever
from app.retrievers.page_fetcher import fetch_page_text
from app.services.provenance import AUTHORITATIVE_HOST_DOMAINS, classify as classify_provenance, is_authoritative

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

#: Tavily ``include_domains`` whitelist, so the search targets statistical
#: bodies, courts, and filing registries rather than generic reporting.
_OFFICIAL_DOMAINS = tuple(AUTHORITATIVE_HOST_DOMAINS)

_TAVILY_ENDPOINT = "https://api.tavily.com/search"


class PrimarySourceRetriever(Retriever):
    """Retrieve primary or authoritative records for a subclaim.

    The channel does not need its own API key: it shares the web-search
    (Tavily) credentials and restricts results to official domains. Dedicated
    ``PRIMARY_SOURCE_*`` settings, when set, override the shared ones.

    ``SEARCH_FAILED`` is reported distinctly from ``NOT_FOUND`` so a missing
    primary source is never confused with a search that could not run.
    """

    channel_name = SearchChannel.PRIMARY_SOURCE.value

    def __init__(self):
        self.last_status = "NOT_CONFIGURED"

    @staticmethod
    def _publisher_from_url(url: str | None) -> str:
        if not url:
            return "Unknown publisher"
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path or ""
        host = host.replace("www.", "")
        return host.split(":")[0] or "Unknown publisher"

    def is_available(self) -> bool:
        return bool(
            settings.PRIMARY_SOURCE_API_KEY
            or settings.WEB_SEARCH_API_KEY
        )

    def _api_key(self) -> str | None:
        return settings.PRIMARY_SOURCE_API_KEY or settings.WEB_SEARCH_API_KEY

    def _endpoint(self) -> str:
        return settings.PRIMARY_SOURCE_ENDPOINT or settings.WEB_SEARCH_ENDPOINT or _TAVILY_ENDPOINT

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

        api_key = self._api_key()
        if not api_key:
            self.last_status = "NOT_CONFIGURED"
            return []

        max_results = int(kwargs.get("max_results", settings.PRIMARY_SOURCE_MAX_RESULTS))
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        body: dict[str, Any] = {
            "query": query,
            "search_depth": kwargs.get("search_depth") or "advanced",
            "topic": kwargs.get("topic") or "general",
            "max_results": max_results,
            "include_domains": list(_OFFICIAL_DOMAINS),
        }

        try:
            response = httpx.post(
                self._endpoint(),
                json=body,
                headers=headers,
                timeout=float(kwargs.get("timeout", settings.GDELT_TIMEOUT_SECONDS)),
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            logger.info("Primary source search failed for %r: %s", query, exc)
            self.last_status = "SEARCH_FAILED"
            return []

        items = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            self.last_status = "NOT_FOUND"
            return []

        normalized: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or ""
            title = item.get("title") or "Untitled"
            publisher = item.get("publisher") or item.get("source") or self._publisher_from_url(url)

            # Only keep results that are authoritative records; the channel must
            # never contribute generic reporting to the pool.
            declared = self.classify(url, title, publisher)
            assessment = classify_provenance(url=url, source_type=declared.value, publisher=publisher, title=title)
            if not is_authoritative(assessment):
                continue

            content = item.get("content") or item.get("snippet") or item.get("description") or ""
            body_text = fetch_page_text(url) if url else None

            normalized.append(
                {
                    "title": title,
                    "url": url,
                    "publisher": publisher,
                    "publication_date": item.get("published") or item.get("published_date") or item.get("date"),
                    "content": body_text or content,
                    "retrieval_channel": self.channel_name,
                    "source_type": declared.value,
                    "query": query,
                    "metadata": {
                        "provider": "tavily",
                        "is_primary_channel": True,
                        "full_text_fetched": bool(body_text),
                    },
                }
            )

        self.last_status = "FOUND" if normalized else "NOT_FOUND"
        return normalized