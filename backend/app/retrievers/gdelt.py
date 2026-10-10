from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any

import httpx

from app.config import settings
from app.models import SearchChannel
from app.retrievers.base import Retriever, SearchResult

logger = logging.getLogger(__name__)

#: GDELT throttles by client IP (~one request every five seconds) and answers a
#: 429 with a plain-text body. Requests are serialised process-wide and retried
#: so a burst of discovery queries does not silently produce zero documents.
_RATE_LIMIT_MARKER = "please limit requests"
_THROTTLE_LOCK = threading.Lock()
_last_request_at = 0.0

#: Circuit breaker: after enough consecutive 429s the shared IP is treated as
#: exhausted and GDELT is skipped until the cooldown elapses. Without this a
#: rate-limited run pays the full throttle-and-retry cost on every query and
#: still collects nothing.
_consecutive_rate_limits = 0
_breaker_open_until = 0.0


def reset_rate_limit_state() -> None:
    """Reset throttle and breaker state. Intended for tests and manual recovery."""
    global _last_request_at, _consecutive_rate_limits, _breaker_open_until
    with _THROTTLE_LOCK:
        _last_request_at = 0.0
        _consecutive_rate_limits = 0
        _breaker_open_until = 0.0


def _breaker_is_open() -> bool:
    return time.monotonic() < _breaker_open_until


def _register_rate_limit() -> None:
    global _consecutive_rate_limits, _breaker_open_until
    threshold = max(1, int(settings.GDELT_BREAKER_THRESHOLD))
    with _THROTTLE_LOCK:
        _consecutive_rate_limits += 1
        if _consecutive_rate_limits >= threshold and _breaker_open_until <= time.monotonic():
            _breaker_open_until = time.monotonic() + max(0.0, float(settings.GDELT_BREAKER_COOLDOWN_SECONDS))
            logger.warning(
                "GDELT circuit breaker opened for %.0fs after %d consecutive rate-limited requests",
                settings.GDELT_BREAKER_COOLDOWN_SECONDS,
                _consecutive_rate_limits,
            )


def _register_success() -> None:
    global _consecutive_rate_limits, _breaker_open_until
    with _THROTTLE_LOCK:
        _consecutive_rate_limits = 0
        _breaker_open_until = 0.0


def _respect_rate_limit() -> None:
    global _last_request_at
    interval = max(0.0, float(settings.GDELT_MIN_INTERVAL_SECONDS))
    with _THROTTLE_LOCK:
        wait = interval - (time.monotonic() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()


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

        days = max(1, int(kwargs.get("time_range_days", settings.GDELT_TIMESPAN_DAYS)))
        params = {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": int(kwargs.get("max_results", settings.GDELT_MAX_RESULTS)),
            "timespan": f"{days}d",
        }
        language = kwargs.get("language") or settings.GDELT_LANGUAGE
        if language:
            params["lang"] = language

        timeout = float(kwargs.get("timeout", settings.GDELT_TIMEOUT_SECONDS))
        attempts = 1 + max(0, int(settings.GDELT_MAX_RETRIES))
        for attempt in range(attempts):
            if _breaker_is_open():
                logger.info("GDELT circuit breaker open; skipping %r", query)
                return []
            _respect_rate_limit()
            try:
                response = httpx.get(settings.GDELT_API_URL, params=params, timeout=timeout)
            except Exception as exc:  # noqa: BLE001
                logger.info("GDELT request failed for %r: %s", query, exc)
                return []

            body = response.text or ""
            if response.status_code == 429 or _RATE_LIMIT_MARKER in body.lower():
                _register_rate_limit()
                if attempt + 1 < attempts and not _breaker_is_open():
                    logger.info("GDELT rate limited for %r; backing off", query)
                    continue
                logger.warning("GDELT rate limited for %r; gave up after %d attempts", query, attempt + 1)
                return []
            if response.status_code >= 400:
                logger.info("GDELT returned HTTP %s for %r", response.status_code, query)
                return []

            _register_success()

            try:
                payload = response.json()
            except Exception:  # noqa: BLE001
                logger.info("GDELT returned a non-JSON body for %r", query)
                return []

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

        return []
