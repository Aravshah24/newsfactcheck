from __future__ import annotations

import hashlib
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.models import Document, Publisher, PublisherType


class DocumentNormalizer:
    @staticmethod
    def normalize_url(url: str | None) -> str | None:
        if not url:
            return None
        parsed = urlsplit(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path or "/"
        normalized = f"{scheme}://{netloc}{path}"
        if parsed.query:
            normalized = f"{normalized}?{parsed.query}"
        return normalized.rstrip("/") or "https://"

    @staticmethod
    def content_hash(text: str | None) -> str | None:
        if not text:
            return None
        normalized = text.strip().lower().encode("utf-8")
        return hashlib.sha256(normalized).hexdigest()

    @staticmethod
    def get_or_create_publisher(session: Session, name: str | None, domain: str | None = None) -> Publisher:
        cleaned_name = (name or "Unknown publisher").strip() or "Unknown publisher"
        publisher = session.query(Publisher).filter(Publisher.name == cleaned_name).first()
        if publisher:
            return publisher

        publisher = Publisher(
            name=cleaned_name,
            domain=domain,
            publisher_type=PublisherType.NEWS,
        )
        session.add(publisher)
        session.flush()
        return publisher

    @classmethod
    def normalize_document(cls, session: Session, result: dict, claim_id: int | None = None, subclaim_id: int | None = None) -> Document:
        url = cls.normalize_url(result.get("url"))
        canonical_url = cls.normalize_url(result.get("canonical_url") or url)
        title = result.get("title") or "Untitled"
        publisher_name = result.get("publisher") or "Unknown publisher"
        domain = result.get("domain") or (urlsplit(url).netloc if url else None)
        publisher = cls.get_or_create_publisher(session, publisher_name, domain)

        existing = None
        for pending in session.new:
            if isinstance(pending, Document):
                if url and pending.url == url:
                    existing = pending
                    break
                if canonical_url and pending.canonical_url == canonical_url:
                    existing = pending
                    break
        if url:
            existing = session.query(Document).filter(Document.url == url).first()
        if existing is None and canonical_url:
            existing = session.query(Document).filter(Document.canonical_url == canonical_url).first()
        if existing is not None:
            return existing

        document = Document(
            publisher_id=publisher.id,
            url=url or "https://unknown.example",
            canonical_url=canonical_url,
            normalized_url=url,
            title=title,
            source_type=result.get("source_type") or "news",
            content_hash=cls.content_hash(result.get("content") or title),
            text_content=result.get("content") or title,
            extra_metadata={**result.get("metadata", {}), "claim_id": claim_id, "subclaim_id": subclaim_id},
        )
        session.add(document)
        session.flush()
        return document
