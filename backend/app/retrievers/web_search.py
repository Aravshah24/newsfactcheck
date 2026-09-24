from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.retrievers.base import Retriever


class WebSearchRetriever(Retriever):
    channel_name = "web_search"

    @staticmethod
    def _publisher_from_url(url: str | None) -> str:
        if not url:
            return "Unknown publisher"
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path or ""
        host = host.replace("www.", "")
        return host.split(":")[0] or "Unknown publisher"

    def is_available(self) -> bool:
        provider = (settings.WEB_SEARCH_PROVIDER or "").lower()
        if not provider or provider in {"mock", "none"}:
            return False
        if provider == "tavily":
            return bool(settings.WEB_SEARCH_ENDPOINT and settings.WEB_SEARCH_API_KEY)
        if provider == "tavily":
            return bool(settings.WEB_SEARCH_ENDPOINT and settings.WEB_SEARCH_API_KEY)
        return bool(settings.WEB_SEARCH_ENDPOINT or settings.WEB_SEARCH_API_KEY)

    def search(self, subclaim: Any | None, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        provider = (settings.WEB_SEARCH_PROVIDER or "").lower()
        if not self.is_available() or provider in {"mock", "none"}:
            return []

        endpoint = settings.WEB_SEARCH_ENDPOINT
        if not endpoint:
            return []

        headers: dict[str, str] = {"Accept": "application/json"}

        if provider == "tavily":
            if not settings.WEB_SEARCH_API_KEY:
                raise RuntimeError("WEB_SEARCH_API_KEY is required when WEB_SEARCH_PROVIDER=tavily.")
            headers["Authorization"] = f"Bearer {settings.WEB_SEARCH_API_KEY}"
            body: dict[str, Any] = {
                "query": query,
                "search_depth": kwargs.get("search_depth") or "basic",
                "topic": kwargs.get("topic") or "news",
                "max_results": int(kwargs.get("max_results", 5)),
            }
            try:
                response = httpx.post(
                    endpoint,
                    json=body,
                    headers=headers,
                    timeout=float(kwargs.get("timeout", 10.0)),
                )
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                raise RuntimeError(f"Tavily web search request failed: {exc}") from exc

            items = payload.get("results") if isinstance(payload, dict) else []
            if not isinstance(items, list):
                items = []
        else:
            params: dict[str, Any] = {"q": query, "num": int(kwargs.get("max_results", 5))}
            if settings.WEB_SEARCH_API_KEY:
                headers["Authorization"] = f"Bearer {settings.WEB_SEARCH_API_KEY}"
            try:
                response = httpx.get(
                    endpoint,
                    params=params,
                    headers=headers,
                    timeout=float(kwargs.get("timeout", 10.0)),
                )
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                raise RuntimeError(f"Web search request failed for provider '{provider}': {exc}") from exc

            items: list[Any] = []
            if isinstance(payload, dict):
                for key in ("results", "items", "organic_results", "data"):
                    value = payload.get(key)
                    if isinstance(value, list):
                        items = value
                        break
            elif isinstance(payload, list):
                items = payload

        normalized: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            standardized = {
                "title": item.get("title") or item.get("name") or "Web result",
                "url": item.get("url") or item.get("link") or "",
                "publisher": item.get("publisher") or item.get("source") or item.get("site") or self._publisher_from_url(item.get("url") or ""),
                "publication_date": item.get("published") or item.get("published_date") or item.get("published_at") or item.get("date"),
                "content": item.get("content") or item.get("snippet") or item.get("description") or "",
                "retrieval_channel": self.channel_name,
                "query": query,
                "metadata": {"provider": provider},
            }
            normalized.append(standardized)
        return normalized
