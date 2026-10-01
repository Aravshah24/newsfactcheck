from __future__ import annotations

import hashlib
import logging
import re
from urllib.parse import urlsplit

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Document, SourceRelationship, SourceRelationshipType

logger = logging.getLogger(__name__)

_TRACKING_PARAM_RE = re.compile(
    r"^(?:utm_[a-z]+|fbclid|gclid|mc_cid|mc_eid|ref|ref_src|igshid|spm|at_|CMP|ito|ns_|smid|sr_share)$",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Boilerplate shared by most templated news pages. Removed before similarity
# comparison so that two syndication copies of the same story compare equal even
# when their navigation and footer text differs.
_BOILERPLATE_MARKERS = (
    "subscribe", "newsletter", "sign in", "log in", "advertisement", "cookie",
    "privacy policy", "terms of service", "all rights reserved", "share this",
    "read more", "follow us", "contact us", "copyright",
)


def canonical_url_key(url: str | None) -> str | None:
    """Reduce a URL to a comparison key by dropping scheme, www, and tracking params."""
    if not url:
        return None
    parsed = urlsplit(url.strip())
    netloc = (parsed.netloc or "").lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    if not netloc:
        return None
    query_pairs = [
        (key, value)
        for key, value in _parse_query(parsed.query)
        if not _TRACKING_PARAM_RE.match(key)
    ]
    query = "&".join(f"{key}={value}" for key, value in sorted(query_pairs))
    path = (parsed.path or "/").rstrip("/") or "/"
    return f"{netloc}{path}" + (f"?{query}" if query else "")


def _parse_query(query: str) -> list[tuple[str, str]]:
    if not query:
        return []
    pairs: list[tuple[str, str]] = []
    for chunk in query.split("&"):
        if not chunk:
            continue
        key, _, value = chunk.partition("=")
        pairs.append((key, value))
    return pairs


def shingles(text: str | None, size: int = 5) -> set[str]:
    """Word n-gram set used for near-duplicate detection."""
    if not text:
        return set()
    lowered = text.lower()
    for marker in _BOILERPLATE_MARKERS:
        lowered = lowered.replace(marker, " ")
    tokens = _TOKEN_RE.findall(lowered)
    if len(tokens) < size:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[index : index + size]) for index in range(len(tokens) - size + 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    intersection = len(left & right)
    if not intersection:
        return 0.0
    return intersection / len(left | right)


def near_duplicate_score(left: Document, right: Document) -> float:
    """Similarity between two documents, combining title, body, and URL signals."""
    title_score = jaccard(shingles(getattr(left, "title", None), 3), shingles(getattr(right, "title", None), 3))
    body_score = jaccard(
        shingles(getattr(left, "text_content", None)),
        shingles(getattr(right, "text_content", None)),
    )
    left_key = canonical_url_key(getattr(left, "url", None))
    right_key = canonical_url_key(getattr(right, "url", None))
    url_score = 1.0 if left_key and left_key == right_key else 0.0
    return max(url_score, (0.5 * title_score) + (0.5 * body_score))


class DeduplicationService:
    """Collapse duplicate and republished documents and record the relationship."""

    #: Similarity at or above this value marks two documents as syndicated copies.
    NEAR_DUPLICATE_THRESHOLD = 0.72

    @staticmethod
    def resolve_duplicate_document(session: Session, document: Document) -> Document | None:
        """Return the single representative document for this document's URL.

        Older data can contain several rows sharing one URL. The representative is
        always the lowest id in the group, so the answer does not depend on which
        member of the group is being checked. Returning an arbitrary member instead
        would let two members of the same group survive as separate documents.
        """
        if not document.url:
            return None

        candidates: dict[int, Document] = {}

        def collect(rows) -> None:
            for row in rows:
                if row.id != document.id:
                    candidates[row.id] = row

        collect(session.query(Document).filter(Document.url == document.url).all())
        if document.canonical_url:
            collect(
                session.query(Document)
                .filter(Document.canonical_url == document.canonical_url)
                .all()
            )

        key = canonical_url_key(document.url)
        if key:
            for candidate in session.query(Document).all():
                if canonical_url_key(candidate.url) == key:
                    collect([candidate])

        if not candidates:
            return None
        return candidates[min(candidates)]

    @staticmethod
    def create_obvious_relationships(
        session: Session,
        source: Document,
        target: Document,
        relationship_type: SourceRelationshipType,
        justification: str,
        confidence: float = 0.9,
    ) -> Document | None:
        if source.id == target.id:
            return None

        existing = (
            session.query(SourceRelationship)
            .filter(
                SourceRelationship.source_document_id == source.id,
                SourceRelationship.target_document_id == target.id,
                SourceRelationship.relationship_type == relationship_type,
            )
            .first()
        )
        if existing:
            return None

        try:
            # A savepoint keeps the failure contained to this one insert, so a
            # duplicate edge never discards the documents gathered so far.
            with session.begin_nested():
                session.add(
                    SourceRelationship(
                        source_document_id=source.id,
                        target_document_id=target.id,
                        relationship_type=relationship_type,
                        confidence=round(float(confidence), 2),
                        evidence_justification=justification,
                    )
                )
        except IntegrityError:
            # A concurrent pass may have recorded the same edge. That is harmless.
            logger.info("Skipped duplicate %s edge %s -> %s", relationship_type, source.id, target.id)
        return target

    @classmethod
    def _classify_pair(cls, source: Document, target: Document) -> tuple[SourceRelationshipType | None, str, float]:
        if source.url and target.url and source.url == target.url:
            return SourceRelationshipType.COPIED_FROM, "Identical document URL.", 1.0
        if source.canonical_url and target.canonical_url and source.canonical_url == target.canonical_url:
            return SourceRelationshipType.COPIED_FROM, "Identical canonical URL.", 1.0
        if source.content_hash and target.content_hash and source.content_hash == target.content_hash:
            return SourceRelationshipType.SYNDICATED_FROM, "Identical content hash.", 1.0

        left_key = canonical_url_key(source.url)
        right_key = canonical_url_key(target.url)
        if left_key and left_key == right_key:
            return SourceRelationshipType.COPIED_FROM, "Same URL after removing tracking parameters.", 0.95

        score = near_duplicate_score(source, target)
        if score >= cls.NEAR_DUPLICATE_THRESHOLD:
            return (
                SourceRelationshipType.SYNDICATED_FROM,
                f"Near-duplicate text similarity {score:.2f}.",
                round(score, 2),
            )
        return None, "", score

    @staticmethod
    def normalize_and_dedupe(
        session: Session, documents: list[Document], collapse_near_duplicates: bool = True
    ) -> list[Document]:
        """Return the deduplicated document list and record syndication edges.

        Collapsed documents are still persisted (they remain retrievable through
        their relationship edges) but they are removed from the list that feeds
        evidence extraction, so a republished article cannot be counted as a
        second independent item.
        """
        unique: list[Document] = []
        seen: set[int] = set()

        for document in documents:
            duplicate = DeduplicationService.resolve_duplicate_document(session, document)
            if duplicate is not None:
                if duplicate.id not in seen:
                    unique.append(duplicate)
                    seen.add(duplicate.id)
                continue
            if document.id not in seen:
                unique.append(document)
                seen.add(document.id)

        survivors: list[Document] = []
        for document in unique:
            merged_into = None
            for index, existing in enumerate(survivors):
                relationship_type, justification, score = DeduplicationService._classify_pair(existing, document)
                if relationship_type is None:
                    continue
                if relationship_type is SourceRelationshipType.SYNDICATED_FROM and not collapse_near_duplicates:
                    continue
                DeduplicationService.create_obvious_relationships(
                    session,
                    document,
                    existing,
                    relationship_type,
                    justification,
                    confidence=score,
                )
                merged_into = index
                break
            if merged_into is None:
                survivors.append(document)
            else:
                session.flush()

        return survivors
