from __future__ import annotations

from pydantic import BaseModel, Field

from app.models import EvidenceStance, VerificationVerdict
from app.services.llm import LLMClient


class VerificationSchema(BaseModel):
    verdict: str = VerificationVerdict.INSUFFICIENT_EVIDENCE.value
    confidence: float = 0.4
    rationale: str = ""
    supporting_evidence_count: int = 0
    contradicting_evidence_count: int = 0
    context_evidence_count: int = 0
    primary_evidence_status: str = "NOT_FOUND"
    method: str = "llm_evidence_review"


class VerificationAgent:
    """Phase 1 evidence-based verdicting based on evidence strength, contradictions, and completeness."""

    @staticmethod
    def _stance_value(item) -> str:
        stance = getattr(item, "stance", "unknown")
        return str(getattr(stance, "value", stance)).lower()

    def verify(
        self,
        subclaim,
        evidence_items: list | None = None,
        completeness_result: dict | None = None,
        primary_status: str = "NOT_FOUND",
        independence_summary: dict | None = None,
    ) -> dict:
        items = evidence_items or []
        supporting = [item for item in items if self._stance_value(item) == EvidenceStance.SUPPORTS.value]
        contradicting = [item for item in items if self._stance_value(item) == EvidenceStance.CONTRADICTS.value]
        context = [item for item in items if self._stance_value(item) == EvidenceStance.CONTEXT.value]
        completeness = completeness_result or {"completeness_status": "UNKNOWN", "missing_context": []}

        try:
            evidence_text = "\n".join(
                f"- {getattr(item, 'summary', str(item))} [{self._stance_value(item)}]"
                for item in items[:20]
            ) or "No evidence items were supplied to the model."
            response = LLMClient().generate_structured(
                VerificationSchema,
                f"Evaluate the subclaim using only the supplied evidence. Do not use background knowledge.\n\nSUBCLAIM:\n{getattr(subclaim, 'text', str(subclaim))}\n\nEVIDENCE:\n{evidence_text}\n\nCOMPLETENESS:\n{completeness}\n\nPRIMARY_STATUS:\n{primary_status}\n\nINDEPENDENCE:\n{independence_summary}",
                system_prompt="Return JSON only with: verdict, confidence, rationale, supporting_evidence_count, contradicting_evidence_count, context_evidence_count, primary_evidence_status, method. Use only the explicit evidence and context from the prompt."
            )
            result = response.model_dump() if hasattr(response, "model_dump") else dict(response)
            if isinstance(result, dict) and result.get("verdict"):
                return {
                    "subclaim_id": getattr(subclaim, "id", None),
                    "subclaim_text": getattr(subclaim, "text", None),
                    **result,
                    "supporting_evidence_count": len(supporting),
                    "contradicting_evidence_count": len(contradicting),
                    "context_evidence_count": len(context),
                }
        except Exception:
            pass

        support_count = len(supporting)
        contradict_count = len(contradicting)

        if completeness.get("completeness_status") in {"MISLEADING_BY_OMISSION", "INCOMPLETE"} and support_count > 0:
            verdict = VerificationVerdict.MISLEADING_OR_INCOMPLETE.value
            confidence = 0.72
            rationale = "The evidence is partly supportive, but the claim appears incomplete or misleading without the required context."
        elif support_count == 0 and contradict_count == 0:
            verdict = VerificationVerdict.INSUFFICIENT_EVIDENCE.value
            confidence = 0.32
            rationale = "There is not enough direct evidence to support or dispute the subclaim at this stage."
        elif contradict_count > support_count:
            verdict = VerificationVerdict.DISPUTED.value
            confidence = min(0.9, 0.5 + (contradict_count * 0.12))
            rationale = "Contradicting evidence is stronger than the supporting evidence or appears materially inconsistent."
        elif support_count > 0 and contradict_count == 0:
            verdict = VerificationVerdict.SUPPORTED.value
            confidence = min(0.95, 0.55 + (support_count * 0.12))
            rationale = "The subclaim is supported by the retrieved evidence and no material contradictions were identified."
        elif support_count > 0 and contradict_count > 0:
            verdict = VerificationVerdict.PARTIALLY_SUPPORTED.value
            confidence = min(0.8, 0.5 + (support_count * 0.08) - (contradict_count * 0.05))
            rationale = "The evidence is mixed and should be interpreted as partially supported rather than conclusively established."
        else:
            verdict = VerificationVerdict.UNVERIFIABLE.value
            confidence = 0.25
            rationale = "The evidence base is too thin or too context-dependent for a stable verdict."

        if primary_status == "FOUND":
            confidence = min(0.99, confidence + 0.08)
        elif primary_status == "SEARCH_FAILED":
            confidence = max(0.1, confidence - 0.06)

        if independence_summary:
            independent_groups = independence_summary.get("estimated_independent_sources", 1)
            if independent_groups <= 1 and verdict == VerificationVerdict.SUPPORTED.value:
                verdict = VerificationVerdict.PARTIALLY_SUPPORTED.value
                rationale = "The support appears narrow, and the evidence may be overly concentrated in a few overlapping sources."
            confidence = max(0.1, min(0.99, confidence - max(0.0, (1 - independent_groups) * 0.15)))

        return {
            "subclaim_id": getattr(subclaim, "id", None),
            "subclaim_text": getattr(subclaim, "text", None),
            "verdict": verdict,
            "confidence": round(confidence, 2),
            "rationale": rationale,
            "supporting_evidence_count": support_count,
            "contradicting_evidence_count": contradict_count,
            "context_evidence_count": len(context),
            "primary_evidence_status": primary_status,
            "method": "heuristic_evidence_review",
        }
