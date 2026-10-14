"""Retrieval abstractions and channel-specific implementations."""

from app.retrievers.base import Retriever, SearchResult
from app.retrievers.crawler import CrawlerRetriever, crawl_urls
from app.retrievers.gdelt import GDELTRetriever
from app.retrievers.page_fetcher import fetch_page_text
from app.retrievers.primary_source import PrimarySourceRetriever
from app.retrievers.web_search import WebSearchRetriever

__all__ = [
    "Retriever",
    "SearchResult",
    "CrawlerRetriever",
    "crawl_urls",
    "GDELTRetriever",
    "fetch_page_text",
    "PrimarySourceRetriever",
    "WebSearchRetriever",
]