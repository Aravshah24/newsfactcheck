from __future__ import annotations

import logging

from app.config import settings
from app.models import EvidenceStance
from app.services.evidence_stance import normalise_stance
from app.services.llm import LLMClient, LLMUnavailableError

logger = logging.getLogger(__name__)

_WRITER_INSTRUCTION = """Write a concise fact-check report using only the supplied structured data.

Rules you must follow:
1. Keep every verdict and confidence value exactly as given. Do not upgrade or soften them.
2. Do not add facts, sources, figures, or dates that are not in the supplied data.
3. Do not describe a document as confirming or contradicting anything unless its recorded
   stance says so.
4. If the evidence is thin, say so plainly.
5. Use plain prose. No markdown headings, no bullet lists of invented content.

Return the report body only."""


class WriterAgent:
    """Render an evidence-constrained final report.

    The writer never changes a computed verdict and never introduces a fact that
    is not present in the evidence, completeness, independence, and verification
    data it is given.
    """

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or LLMClient()

    def write(
        self,
        claim_text: str,
        subclaims: list,
        overall_verdict: dict,
        completeness_result: dict,
        evidence_items: list,
        documents: list,
        media_analysis: dict,
        independence_summary: dict,
        verification_results: list,
        primary_status: str = "NOT_SEARCHED",
    ) -> str:
        summary_text = overall_verdict.get("explanation") or (
            "The conclusion is based on the available evidence and any uncertainty is disclosed."
        )

        if self.llm.is_configured():
            try:
                summary_text = self.llm.generate(
                    "CLAIM:\n%s\n\nOVERALL VERDICT:\n%s\n\nCOMPLETENESS:\n%s\n\n"
                    "SOURCE INDEPENDENCE:\n%s\n\nPRIMARY EVIDENCE STATUS: %s\n\n"
                    "MEDIA ANALYSIS:\n%s\n\nVERIFICATION RESULTS:\n%s"
                    % (
                        claim_text,
                        overall_verdict,
                        completeness_result,
                        independence_summary,
                        primary_status,
                        media_analysis,
                        verification_results,
                    ),
                    system_prompt=_WRITER_INSTRUCTION,
                )
            except LLMUnavailableError as exc:
                logger.info("Report summary fell back to the computed explanation: %s", exc)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Report summary generation failed: %s", exc)

        lines = [
            "================================================",
            "",
            "CLAIM",
            str(claim_text),
            "",
            "OVERALL VERDICT",
            str(overall_verdict.get("overall_verdict", "UNKNOWN")).upper(),
            f"Confidence: {float(overall_verdict.get('overall_confidence', 0.0)):.2f}",
            "",
            "SUMMARY",
            summary_text,
            "",
        ]

        for index, subclaim in enumerate(subclaims, start=1):
            verdict = next(
                (item for item in verification_results if str(item.get("subclaim_id")) == str(subclaim.id)),
                {},
            )
            lines.extend(
                [
                    f"---\nSUBCLAIM {index}",
                    f'"{subclaim.text}"',
                    f"Verdict: {str(verdict.get('verdict', 'INSUFFICIENT_EVIDENCE')).upper()}",
                    f"Confidence: {float(verdict.get('confidence', 0.0)):.2f}",
                    "",
                    "Supporting evidence (documents assessed as entailing the complete proposition):",
                ]
            )
            lines.extend(self._stance_lines(evidence_items, subclaim, EvidenceStance.SUPPORTS))

            lines.extend(["", "Contradicting evidence (documents conflicting on at least one dimension):"])
            lines.extend(self._stance_lines(evidence_items, subclaim, EvidenceStance.CONTRADICTS))

            lines.extend(["", "Context only (related but not probative):"])
            lines.extend(self._context_lines(evidence_items, subclaim))

            lines.extend(
                [
                    "",
                    f"Independent supporting source groups: {verdict.get('independent_supporting_groups', 0)}",
                    f"Primary/authoritative evidence: {primary_status}",
                    "",
                    "Reasoning:",
                    verdict.get("rationale") or "Evidence quality, source independence, and completeness were considered.",
                    "",
                ]
            )

        lines.extend(["---", "MISSING CONTEXT"])
        if completeness_result.get("missing_context"):
            lines.extend(f"- {item}" for item in completeness_result["missing_context"])
        else:
            lines.append("- No material missing-context issues were identified in the current review.")

        lines.extend(
            [
                "",
                "---",
                "SOURCE INDEPENDENCE",
                f"Documents retrieved: {independence_summary.get('documents_found', len(documents))}",
                f"Distinct publishers: {independence_summary.get('distinct_publishers', 0)}",
                f"Duplicate or republished documents: {independence_summary.get('duplicate_derived_documents', 0)}",
                f"Independent source groups: {independence_summary.get('independent_groups', 0)}",
                "",
                "---",
                "MEDIA COVERAGE",
                f"Framing summary: {media_analysis.get('framing_summary', 'No framing summary available.')}",
                "",
                "---",
                "SOURCES",
            ]
        )
        for index, document in enumerate(documents[:10], start=1):
            lines.append(f"{index}. {getattr(document, 'title', 'Untitled')} - {getattr(document, 'url', 'unknown')}")

        lines.extend(
            [
                "",
                "---",
                "INVESTIGATION TRACE",
                "Claim analyzed -> searches executed -> opposition searches executed -> primary evidence searched "
                "-> documents deduplicated -> evidence assessed dimension by dimension -> evidence clustered by source "
                "independence -> completeness analyzed -> verification completed -> report generated",
                "",
                "================================================",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _items_for(evidence_items: list, subclaim) -> list:
        return [
            item
            for item in evidence_items
            if str(getattr(item, "subclaim_id", None)) == str(getattr(subclaim, "id", None))
        ]

    def _stance_lines(self, evidence_items: list, subclaim, stance: EvidenceStance) -> list[str]:
        matches = [
            item
            for item in self._items_for(evidence_items, subclaim)
            if normalise_stance(getattr(item, "stance", "unknown")) == stance.value
        ]
        if not matches:
            return ["- None identified."]
        return [f"- {item.url or (item.summary or '')[:100]}" for item in matches[:3]]

    def _context_lines(self, evidence_items: list, subclaim) -> list[str]:
        matches = [
            item
            for item in self._items_for(evidence_items, subclaim)
            if normalise_stance(getattr(item, "stance", "unknown")) in {"context", "neutral", "unknown"}
        ]
        if not matches:
            return ["- None."]
        return [f"- {item.url or (item.summary or '')[:100]}" for item in matches[:3]]
