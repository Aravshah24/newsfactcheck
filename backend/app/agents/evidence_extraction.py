from __future__ import annotations

from app.models import EvidenceAssessmentStatus, EvidenceCategory, EvidenceItem, EvidenceStance


class EvidenceExtractor:
    """Convert source documents into raw evidence attached to a subclaim."""

    def extract(self, subclaim, document, raw_text: str, extraction_method: str = "rule_based") -> EvidenceItem:
        text = (raw_text or document.text_content or subclaim.text or "").strip()
        if not text:
            text = "No extractable text was available."

        summary = text[:512] if len(text) > 512 else text
        stance = self._infer_stance(subclaim.text, text)

        evidence = EvidenceItem(
            claim_id=subclaim.claim_id,
            subclaim_id=subclaim.id,
            document_id=document.id,
            category=EvidenceCategory.RAW,
            stance=stance,
            assessment_status=EvidenceAssessmentStatus.UNASSESSED,
            summary=summary,
            raw_excerpt=text,
            retrieval_channel="retrieval",
            url=document.url,
            extra_metadata={
                "evidence_text": text,
                "extraction_method": extraction_method,
                "source_title": document.title,
            },
        )
        return evidence

    @staticmethod
    def _infer_stance(subclaim_text: str, source_text: str) -> EvidenceStance:
        subclaim_lower = subclaim_text.lower()
        source_lower = source_text.lower()
        if any(token in source_lower for token in ["denied", "rejected", "contradicted", "not supported", "disputed"]) and any(
            token in subclaim_lower for token in ["raised", "approved", "hired", "caused", "increased"]
        ):
            return EvidenceStance.CONTRADICTS
        if any(token in source_lower for token in ["according to", "said", "reported", "described", "confirmed"]) or "support" in source_lower:
            return EvidenceStance.SUPPORTS
        if any(token in source_lower for token in ["background", "context", "timeline", "at the same time", "meanwhile"]):
            return EvidenceStance.CONTEXT
        return EvidenceStance.UNKNOWN
