import httpx
import pytest

from app.config import settings
from app.retrievers import gdelt as gdelt_module
from app.retrievers.gdelt import GDELTRetriever
from app.retrievers.web_search import WebSearchRetriever


@pytest.fixture(autouse=True)
def _no_throttle(monkeypatch):
    monkeypatch.setattr(settings, "GDELT_MIN_INTERVAL_SECONDS", 0.0)
    gdelt_module.reset_rate_limit_state()
    yield
    gdelt_module.reset_rate_limit_state()


def test_gdelt_formats_timespan_and_normalizes(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return httpx.Response(
            200,
            json={"articles": [{"url": "http://example.com/a", "title": "A", "seendate": "20260101120000"}]},
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    results = GDELTRetriever().search(None, "election")

    assert captured["params"]["timespan"] == "7d"
    assert len(results) == 1
    assert results[0]["url"] == "http://example.com/a"
    assert results[0]["publication_date"].year == 2026


def test_gdelt_retries_rate_limit_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, params=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, text="Please limit requests to one every 5 seconds")
        return httpx.Response(200, json={"articles": [{"url": "http://example.com/b", "title": "B"}]})

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(settings, "GDELT_MAX_RETRIES", 2)
    results = GDELTRetriever().search(None, "election")

    assert calls["n"] == 2
    assert [r["url"] for r in results] == ["http://example.com/b"]


def test_gdelt_gives_up_after_max_retries(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, params=None, timeout=None):
        calls["n"] += 1
        return httpx.Response(429, text="Please limit requests to one every 5 seconds")

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(settings, "GDELT_MAX_RETRIES", 2)

    assert GDELTRetriever().search(None, "election") == []
    assert calls["n"] == 3


def test_gdelt_breaker_opens_and_skips_subsequent_requests(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, params=None, timeout=None):
        calls["n"] += 1
        return httpx.Response(429, text="Please limit requests to one every 5 seconds")

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(settings, "GDELT_MAX_RETRIES", 2)
    monkeypatch.setattr(settings, "GDELT_BREAKER_THRESHOLD", 2)
    monkeypatch.setattr(settings, "GDELT_BREAKER_COOLDOWN_SECONDS", 3600.0)

    assert GDELTRetriever().search(None, "election") == []
    after_first = calls["n"]
    assert GDELTRetriever().search(None, "another") == []
    assert calls["n"] == after_first


def test_gdelt_non_json_body_returns_empty(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(200, text="<html>not json</html>"))
    assert GDELTRetriever().search(None, "election") == []


def test_web_search_unavailable_returns_empty_without_raising(monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setattr(settings, "WEB_SEARCH_ENDPOINT", "https://api.tavily.com/search")
    monkeypatch.setattr(settings, "WEB_SEARCH_API_KEY", None)

    assert WebSearchRetriever().is_available() is False
    assert WebSearchRetriever().search(None, "election") == []
