from __future__ import annotations

from app.config import settings
from app.models import EvidenceStance
from app.services.llm import LLMClient


class WriterAgent:
    """Render a concise evidence-constrained final report without inventing unsupported facts."""

    def write(self, claim_text: str, subclaims: list, overall_verdict: dict, completeness_result: dict, evidence_items: list, documents: list, media_analysis: dict, independence_summary: dict, verification_results: list) -> str:
        summary_text = overall_verdict.get("explanation", "The conclusion is based on the available evidence and uncertainty is disclosed.")
        if settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY:
            try:
                llm = LLMClient()
                prompt = (
                    "Write a concise final report for a news fact-check using only the supplied structured data. "
                    "Keep the computed verdict unchanged, and do not use outside knowledge.\n\n"
                    f"CLAIM:\n{claim_text}\n\n"
                    f"OVERALL VERDICT:\n{overall_verdict}\n\n"
                    f"COMPLETENESS:\n{completeness_result}\n\n"
                    f"SOURCE INDEPENDENCE:\n{independence_summary}\n\n"
                    f"MEDIA ANALYSIS:\n{media_analysis}\n\n"
                    f"VERIFICATION RESULTS:\n{verification_results}"
                )
                summary_text = llm.generate(prompt, system_prompt="Write a concise human-readable report. Preserve the computed verdict and the weighting of the evidence; do not invent new facts.")
            except Exception:
                pass

        lines = [
            "================================================",
            "",
            "CLAIM",
            str(claim_text),
            "",
            "OVERALL VERDICT",
            str(overall_verdict.get("overall_verdict", "UNKNOWN").upper()),
            f"Confidence: {overall_verdict.get('overall_confidence', 0.0):.2f}",
            "",
            "SUMMARY",
            summary_text,
            "",
        ]

        for idx, subclaim in enumerate(subclaims, start=1):
            verdict = next((item for item in verification_results if str(item.get("subclaim_id")) == str(subclaim.id)), {})
            lines.extend([
                f"---\nSUBCLAIM {idx}",
                f'"{subclaim.text}"',
                f"Verdict: {verdict.get('verdict', 'INSUFFICIENT_EVIDENCE').upper()}",
                f"Confidence: {verdict.get('confidence', 0.0):.2f}",
                "",
                "Supporting evidence:",
            ])
            matches = [
                item for item in evidence_items
                if getattr(item, "subclaim_id", None) == subclaim.id
                and str(getattr(getattr(item, "stance", EvidenceStance.UNKNOWN), "value", getattr(item, "stance", EvidenceStance.UNKNOWN))).lower()
                == EvidenceStance.SUPPORTS.value
            ]
            if matches:
                lines.extend([f"- {item.url or item.summary[:100]}" for item in matches[:3]])
            else:
                lines.append("- No direct supporting evidence identified.")

            lines.extend(["", "Contradicting evidence:"])
            matches = [
                item for item in evidence_items
                if getattr(item, "subclaim_id", None) == subclaim.id
                and str(getattr(getattr(item, "stance", EvidenceStance.UNKNOWN), "value", getattr(item, "stance", EvidenceStance.UNKNOWN))).lower()
                == EvidenceStance.CONTRADICTS.value
            ]
            if matches:
                lines.extend([f"- {item.url or item.summary[:100]}" for item in matches[:3]])
            else:
                lines.append("- No material contradictions identified.")

            lines.extend([
                "",
                f"Primary/authoritative evidence: {completeness_result.get('completeness_status', 'UNKNOWN')}",
                "",
                "Reasoning:",
                verdict.get("rationale", "Evidence quality, source independence, and completeness were considered."),
                "",
            ])

        lines.extend([
            "---",
            "MISSING CONTEXT",
        ])
        if completeness_result.get("missing_context"):
            lines.extend([f"- {item}" for item in completeness_result["missing_context"]])
        else:
            lines.append("- No material missing-context issues were identified in the current review.")

        lines.extend([
            "",
            "---",
            "SOURCE INDEPENDENCE",
            f"Documents retrieved: {independence_summary.get('documents_found', len(documents))}",
            f"Distinct publishers: {independence_summary.get('distinct_publishers', 0)}",
            f"Evidence clusters: {independence_summary.get('evidence_clusters', 0)}",
            f"Estimated independent groups: {independence_summary.get('estimated_independent_sources', 0)}",
            "",
            "---",
            "MEDIA COVERAGE",
            f"Framing summary: {media_analysis.get('framing_summary', 'No framing summary available.')}",
            "",
            "---",
            "SOURCES",
        ])
        for idx, doc in enumerate(documents[:10], start=1):
            lines.append(f"{idx}. {getattr(doc, 'title', 'Untitled')} — {getattr(doc, 'url', 'unknown')}")

        lines.extend([
            "",
            "---",
            "INVESTIGATION TRACE",
            "Claim analyzed → searches executed → opposition searches executed → primary evidence searched → documents retrieved → evidence extracted → evidence clustered → completeness analyzed → verification completed → report generated",
            "",
            "================================================",
        ])
        return "\n".join(lines)
