from __future__ import annotations

import logging

from app.config import settings
from app.models import EvidenceAssessmentStatus, EvidenceCategory, EvidenceItem, EvidenceStance
from app.services.entailment import EntailmentEngine, EntailmentResult
from app.services.proposition import Proposition

logger = logging.getLogger(__name__)

_STANCE_MAP = {
    "supports": EvidenceStance.SUPPORTS,
    "contradicts": EvidenceStance.CONTRADICTS,
    "context": EvidenceStance.CONTEXT,
    "neutral": EvidenceStance.NEUTRAL,
    "unknown": EvidenceStance.UNKNOWN,
}


class EvidenceExtractor:
    """Convert a retrieved document into assessed evidence for one subclaim.

    A retrieved document is not evidence. This extractor only records an evidence
    item once the document has been compared against the complete proposition of
    the subclaim along every dimension. Topical overlap alone never yields
    ``SUPPORTS``.
    """

    def __init__(self, engine: EntailmentEngine | None = None):
        self.engine = engine or EntailmentEngine()

    def extract(
        self,
        subclaim,
        document,
        raw_text: str | None = None,
        extraction_method: str | None = None,
        proposition: Proposition | None = None,
        assessment: EntailmentResult | None = None,
    ) -> EvidenceItem:
        text = (raw_text or getattr(document, "text_content", None) or "").strip()
        if not text:
            text = (getattr(document, "title", None) or "").strip()
        title = getattr(document, "title", None)

        prop = proposition or self.engine.proposition_for(getattr(subclaim, "text", str(subclaim)))
        if assessment is None:
            assessment = self.engine.assess(prop, text, title or "")
        result = assessment
        stance = _STANCE_MAP.get(result.stance, EvidenceStance.UNKNOWN)
        method = extraction_method or result.method

        excerpt = text
        limit = max(settings.EVIDENCE_MIN_EXCERPT_CHARS, settings.EVIDENCE_MAX_EXCERPT_CHARS)
        if len(excerpt) > limit:
            excerpt = excerpt[:limit]

        return EvidenceItem(
            claim_id=subclaim.claim_id,
            subclaim_id=subclaim.id,
            document_id=document.id,
            category=EvidenceCategory.AGENT_INTERPRETATION,
            stance=stance,
            assessment_status=EvidenceAssessmentStatus.ASSESSED,
            summary=result.rationale[:512] if result.rationale else title or "Assessed document.",
            raw_excerpt=excerpt or None,
            retrieval_channel="retrieval",
            url=getattr(document, "url", None),
            confidence_score=round(float(result.confidence), 3),
            extra_metadata={
                "evidence_text": text,
                "extraction_method": method,
                "source_title": title,
                "entailment": result.to_dict(),
                "proposition": prop.to_dict(),
            },
        )
