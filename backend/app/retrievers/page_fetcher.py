from __future__ import annotations

import logging
import threading
import time
from html.parser import HTMLParser

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

#: Tags that split text onto a new line when either opened or closed.
_BLOCK_TAGS = {
    "p", "div", "section", "article", "blockquote", "li", "tr",
    "h1", "h2", "h3", "h4", "h5", "h6", "br",
}

#: Tags whose content (markup or scripts) must never reach the extracted text.
_SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "head", "title"}

_USER_AGENT = "Mozilla/5.0 (compatible; NewsFactCheck/0.2; +https://newsfactcheck.localhost)"

_fetch_lock = threading.Lock()
_last_fetch_at: float = 0.0


class _TextExtractor(HTMLParser):
    """Pull the readable body text out of an HTML document.

    Block elements become line breaks, whitespace is collapsed, and content
    inside ``script``/``style``/``head`` is skipped. No dependency outside the
    standard library so the backend gains no third-party parser.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._line_start = True
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        if self._skip_depth:
            return
        if tag in _BLOCK_TAGS:
            self._break_line()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        if self._skip_depth:
            return
        if tag in _BLOCK_TAGS:
            self._break_line()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        for line in data.splitlines():
            words = line.split()
            if not words:
                continue
            if not self._line_start and self._parts and not self._parts[-1].endswith("\n"):
                self._parts.append(" ")
            self._parts.append(" ".join(words))
            self._line_start = False

    def _break_line(self) -> None:
        if self._parts and not self._line_start:
            self._parts.append("\n")
            self._line_start = True

    def extract(self, html: str) -> str:
        self.feed(html or "")
        return "".join(self._parts).strip()


def _throttle() -> None:
    """Serialize page fetches to at least ``PRIMARY_FETCH_INTERVAL_SECONDS``."""
    global _last_fetch_at
    interval = float(settings.PRIMARY_FETCH_INTERVAL_SECONDS)
    with _fetch_lock:
        now = time.monotonic()
        wait = interval - (now - _last_fetch_at)
        if wait > 0:
            time.sleep(wait)
        _last_fetch_at = time.monotonic()


def fetch_page_text(url: str) -> str | None:
    """Best-effort full-page text extraction for a single URL.

    Returns ``None`` on any failure, timeout, or non-HTML response so the caller
    can keep the search snippet. This function never raises.
    """
    if not settings.PRIMARY_FETCH_ENABLED:
        return None

    _throttle()
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        response = httpx.get(
            url,
            headers=headers,
            follow_redirects=True,
            timeout=float(settings.PRIMARY_FETCH_TIMEOUT_SECONDS),
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type.lower():
            return None
        text = _TextExtractor().extract(response.text)
    except Exception as exc:  # noqa: BLE001 - best effort by design
        logger.info("Page fetch failed for %r: %s", url, exc)
        return None

    if not text:
        return None
    limit = int(settings.PRIMARY_FETCH_MAX_CHARS)
    if len(text) > limit:
        logger.debug("Truncated fetched text for %r to %d characters", url, limit)
        text = text[:limit]
    return text