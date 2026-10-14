from __future__ import annotations

import logging
import time
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse, urljoin
from html.parser import HTMLParser

import httpx

from app.config import settings
from app.retrievers.base import Retriever

logger = logging.getLogger(__name__)

# User agent for crawler
_CRAWLER_USER_AGENT = "Mozilla/5.0 (compatible; FactTraceCrawler/1.0; +https://facttrace.localhost)"

# Robots.txt cache
_robots_cache: dict[str, tuple[float, str]] = {}
_robots_lock = threading.Lock()

# Per-domain rate limiting
_domain_last_fetch: dict[str, float] = {}
_domain_lock = threading.Lock()


class _TextExtractor(HTMLParser):
    """Extract readable text from HTML."""

    _BLOCK_TAGS = {
        "p", "div", "section", "article", "blockquote", "li", "tr",
        "h1", "h2", "h3", "h4", "h5", "h6", "br",
    }
    _SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "head", "title"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._line_start = True
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        if self._skip_depth:
            return
        if tag in self._BLOCK_TAGS:
            self._break_line()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        if self._skip_depth:
            return
        if tag in self._BLOCK_TAGS:
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


@dataclass
class RobotsRules:
    allowed: bool
    crawl_delay: float | None
    user_agent: str


def _get_robots_rules(domain: str, user_agent: str = _CRAWLER_USER_AGENT) -> RobotsRules:
    """Fetch and parse robots.txt for a domain."""
    now = time.time()
    with _robots_lock:
        if domain in _robots_cache:
            cached_time, cached_rules = _robots_cache[domain]
            if now - cached_time < 3600:  # Cache for 1 hour
                return RobotsRules(*eval(cached_rules))

    robots_url = f"https://{domain}/robots.txt"
    try:
        response = httpx.get(robots_url, timeout=5.0, follow_redirects=True)
        if response.status_code == 200:
            content = response.text
        else:
            content = ""
    except Exception:
        content = ""

    allowed = True
    crawl_delay = None
    current_ua = None
    for line in content.splitlines():
        line = line.strip()
        if line.lower().startswith("user-agent:"):
            current_ua = line.split(":", 1)[1].strip()
        elif current_ua and (current_ua == "*" or current_ua.lower() == user_agent.lower()):
            if line.lower().startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                if path == "/":
                    allowed = False
            elif line.lower().startswith("crawl-delay:"):
                try:
                    crawl_delay = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass

    rules = RobotsRules(allowed=allowed, crawl_delay=crawl_delay, user_agent=user_agent)
    with _robots_lock:
        _robots_cache[domain] = (now, repr((allowed, crawl_delay, user_agent)))
    return rules


def _respect_crawl_delay(domain: str, crawl_delay: float | None) -> None:
    """Enforce per-domain crawl delay."""
    delay = crawl_delay or getattr(settings, "CRAWLER_MIN_INTERVAL_SECONDS", 2.0)
    with _domain_lock:
        now = time.monotonic()
        last = _domain_last_fetch.get(domain, 0)
        wait = delay - (now - last)
        if wait > 0:
            time.sleep(wait)
        _domain_last_fetch[domain] = time.monotonic()


class CrawlerRetriever(Retriever):
    """Crawler-based retrieval channel.

    Fetches full page content for a list of URLs or searches for URLs
    using a search API and then fetches the content.
    """

    channel_name = "crawler"

    def __init__(self):
        self._extractor = _TextExtractor()

    def is_available(self) -> bool:
        return getattr(settings, "CRAWLER_ENABLED", True)

    def search(self, subclaim: Any | None, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Search for documents using the crawler.

        This retriever operates in two modes:
        1. Direct URL fetching: if `urls` is provided in kwargs, fetch those URLs
        2. Search + fetch: if no URLs, use a search API to find URLs then fetch them

        Args:
            subclaim: The subclaim being investigated
            query: Search query string
            **kwargs: Additional options:
                - urls: list of URLs to fetch directly
                - max_results: maximum number of results
                - search_provider: search API to use ("tavily", "gdelt", or "none")
                - fetch_full_text: whether to fetch full page content
        """
        urls = kwargs.get("urls")
        max_results = int(kwargs.get("max_results", 10))
        fetch_full_text = kwargs.get("fetch_full_text", True)
        search_provider = kwargs.get("search_provider", "tavily")

        results: list[dict[str, Any]] = []

        if urls:
            # Direct URL fetching mode
            urls_list = urls if isinstance(urls, list) else [urls]
            results = self._fetch_urls(urls_list[:max_results], fetch_full_text)
        else:
            # Search + fetch mode
            search_results = self._search_for_urls(query, max_results, search_provider)
            if search_results:
                urls_to_fetch = [r["url"] for r in search_results if r.get("url")]
                fetched = self._fetch_urls(urls_to_fetch[:max_results], fetch_full_text)
                # Merge search metadata with fetched content
                for fetched_result in fetched:
                    matching_search = next(
                        (sr for sr in search_results if sr["url"] == fetched_result["url"]), {}
                    )
                    merged = {**matching_search, **fetched_result}
                    results.append(merged)
            else:
                results = search_results

        return results

    def _search_for_urls(self, query: str, max_results: int, provider: str) -> list[dict[str, Any]]:
        """Search for URLs using a search provider."""
        if provider == "tavily" and settings.WEB_SEARCH_API_KEY and settings.WEB_SEARCH_ENDPOINT:
            return self._tavily_search(query, max_results)
        elif provider == "gdelt" and settings.GDELT_API_URL:
            return self._gdelt_search(query, max_results)
        return []

    def _tavily_search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        """Search using Tavily API."""
        headers = {
            "Authorization": f"Bearer {settings.WEB_SEARCH_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body = {
            "query": query,
            "search_depth": "basic",
            "topic": "news",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        }
        try:
            response = httpx.post(
                settings.WEB_SEARCH_ENDPOINT,
                json=body,
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            payload = response.json()
            items = payload.get("results", [])
            results = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                results.append({
                    "title": item.get("title") or "Web result",
                    "url": item.get("url") or "",
                    "publisher": item.get("publisher") or self._publisher_from_url(item.get("url", "")),
                    "content": item.get("content") or item.get("snippet") or "",
                    "retrieval_channel": self.channel_name,
                    "query": query,
                    "metadata": {"provider": "tavily", "score": item.get("score")},
                })
            return results
        except Exception as exc:
            logger.warning("Tavily search failed: %s", exc)
            return []

    def _gdelt_search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        """Search using GDELT API."""
        # Simplified GDELT search - in practice would use the GDELT retriever
        return []

    def _fetch_urls(self, urls: list[str], fetch_full_text: bool) -> list[dict[str, Any]]:
        """Fetch full page content for a list of URLs."""
        results = []
        for url in urls:
            if not url or not url.startswith(("http://", "https://")):
                continue

            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]

            # Check robots.txt
            rules = _get_robots_rules(domain)
            if not rules.allowed:
                logger.info("Crawler disallowed by robots.txt for %s", domain)
                continue

            # Respect crawl delay
            _respect_crawl_delay(domain, rules.crawl_delay)

            try:
                headers = {
                    "User-Agent": _CRAWLER_USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                }
                timeout = float(getattr(settings, "CRAWLER_TIMEOUT_SECONDS", 15.0))
                response = httpx.get(
                    url,
                    headers=headers,
                    follow_redirects=True,
                    timeout=timeout,
                )
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "html" not in content_type.lower():
                    continue

                html = response.text
                title = self._extract_title(html)
                text = self._extractor.extract(html) if fetch_full_text else ""

                max_chars = int(getattr(settings, "CRAWLER_MAX_CHARS", 8000))
                if text and len(text) > max_chars:
                    text = text[:max_chars]

                results.append({
                    "title": title or "Crawled page",
                    "url": url,
                    "publisher": self._publisher_from_url(url),
                    "publication_date": None,
                    "content": text,
                    "retrieval_channel": self.channel_name,
                    "query": "",
                    "metadata": {
                        "provider": "crawler",
                        "domain": domain,
                        "fetched_at": datetime.utcnow().isoformat(),
                    },
                })
            except Exception as exc:
                logger.info("Crawler fetch failed for %r: %s", url, exc)
                continue

        return results

    def _extract_title(self, html: str) -> str | None:
        """Extract page title from HTML."""
        try:
            import re
            match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        except Exception:
            pass
        return None

    @staticmethod
    def _publisher_from_url(url: str) -> str:
        if not url:
            return "Unknown publisher"
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path or ""
        host = host.replace("www.", "")
        return host.split(":")[0] or "Unknown publisher"


# Convenience function for direct use
def crawl_urls(urls: list[str], max_chars: int = 8000) -> list[dict[str, Any]]:
    """Fetch and extract text from a list of URLs.

    Args:
        urls: List of URLs to crawl
        max_chars: Maximum characters per page

    Returns:
        List of extracted page data
    """
    retriever = CrawlerRetriever()
    return retriever._fetch_urls(urls, fetch_full_text=True)