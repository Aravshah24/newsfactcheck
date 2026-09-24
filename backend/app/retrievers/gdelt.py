from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.config import settings
from app.models import SearchChannel
from app.retrievers.base import Retriever, SearchResult


class GDELTRetriever(Retriever):
    channel_name = SearchChannel.GDELT.value

    @staticmethod
    def normalize_result(item: dict[str, Any]) -> dict[str, Any]:
        url = item.get("url") or item.get("document_url") or item.get("link") or ""
        title = item.get("title") or item.get("name") or "Untitled"
        publisher = item.get("publisher") or item.get("source") or item.get("domain") or "Unknown publisher"
        publication_date = item.get("publication_date") or item.get("publisheddate") or item.get("seendate")
        if isinstance(publication_date, str):
            for fmt in ("%Y%m%d%H%M%S", "%Y%m%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    publication_date = datetime.strptime(publication_date, fmt)
                    break
                except ValueError:
                    continue
        if not isinstance(publication_date, datetime):
            publication_date = None

        return {
            "title": title,
            "url": url,
            "publisher": publisher,
            "publication_date": publication_date,
            "content": item.get("content") or item.get("snippet") or "",
            "retrieval_channel": SearchChannel.GDELT.value,
            "query": item.get("query") or "",
            "metadata": {
                "language": item.get("language") or item.get("lang"),
                "source_country": item.get("sourcecountry"),
                "domain": item.get("domain"),
            },
        }

    def search(self, subclaim: Any | None, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        if not query:
            return []

        params = {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": int(kwargs.get("max_results", settings.GDELT_MAX_RESULTS)),
            "timespan": int(kwargs.get("time_range_days", settings.GDELT_TIMESPAN_DAYS)),
            "lang": kwargs.get("language") or settings.GDELT_LANGUAGE,
        }
        if kwargs.get("language") in (None, ""):
            params.pop("lang", None)

        try:
            response = httpx.get(
                settings.GDELT_API_URL,
                params=params,
                timeout=float(kwargs.get("timeout", settings.GDELT_TIMEOUT_SECONDS)),
            )
            response.raise_for_status()
        except Exception:
            return []

        payload = response.json()
        articles = payload.get("articles") or payload.get("hits") or []
        if not articles:
            return []

        normalized: list[dict[str, Any]] = []
        for item in articles:
            if not isinstance(item, dict):
                continue
            item = {**item, "query": query}
            normalized.append(self.normalize_result(item))
        return normalized
