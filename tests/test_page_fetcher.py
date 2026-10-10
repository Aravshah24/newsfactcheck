from unittest.mock import patch

import httpx

from app.retrievers.page_fetcher import fetch_page_text


def _response(html: str, content_type: str = "text/html") -> httpx.Response:
    response = httpx.Response(
        200,
        text=html,
        request=httpx.Request("GET", "https://data.gov/records/1"),
    )
    response.headers["content-type"] = content_type
    return response


def test_page_fetcher_extracts_plain_text_from_html() -> None:
    html = (
        "<html><head><title>Ignored</title><style>.a{}</style></head><body>"
        "<h1>Census bulletin</h1><p>Hello  world.</p><p>Second sentence.</p>"
        "<script>alert('x')</script></body></html>"
    )
    with patch("app.retrievers.page_fetcher.httpx.get", return_value=_response(html)):
        text = fetch_page_text("https://data.gov/records/1")

    assert text is not None
    assert "Census bulletin" in text
    assert "Hello world." in text
    assert "Second sentence." in text
    # Style and script content must never leak into the extracted text.
    assert ".a{}" not in text
    assert "alert" not in text


def test_page_fetcher_returns_none_on_network_failure() -> None:
    with patch("app.retrievers.page_fetcher.httpx.get", side_effect=RuntimeError("timeout")):
        assert fetch_page_text("https://data.gov/records/1") is None


def test_page_fetcher_returns_none_for_non_html_responses() -> None:
    with patch(
        "app.retrievers.page_fetcher.httpx.get",
        return_value=_response("not html", content_type="application/pdf"),
    ):
        assert fetch_page_text("https://data.gov/records/1.pdf") is None


def test_page_fetcher_returns_none_when_disabled() -> None:
    with patch("app.retrievers.page_fetcher.settings.PRIMARY_FETCH_ENABLED", False), patch(
        "app.retrievers.page_fetcher.httpx.get"
    ) as mock_get:
        assert fetch_page_text("https://data.gov/records/1") is None
    mock_get.assert_not_called()


def test_page_fetcher_caps_long_documents() -> None:
    long_html = "<p>" + ("word " * 10000) + "</p>"
    with patch("app.retrievers.page_fetcher.settings.PRIMARY_FETCH_MAX_CHARS", 100), patch(
        "app.retrievers.page_fetcher.httpx.get", return_value=_response(long_html)
    ):
        text = fetch_page_text("https://data.gov/records/1")

    assert text is not None
    assert len(text) <= 100