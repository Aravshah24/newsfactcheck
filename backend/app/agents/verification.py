from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from app.models import EvidenceStance, VerificationVerdict
from app.services.evidence_stance import normalise_stance
from app.services.llm import LLMClient, LLMUnavailableError

logger = logging.getLogger(__name__)

# Maximum confidence a verdict may carry for a given independent-group count.
# Article volume alone must never be able to produce high confidence.
def _independence_ceiling(independent_groups: int) -> float:
    if independent_groups <= 0:
        return 0.35
    if independent_groups == 1:
        return 0.62
    if independent_groups == 2:
        return 0.78
    return 0.90


_VERDICT_INSTRUCTION = """You are adjudicating one subclaim against assessed evidence.

Every evidence item has already been compared with the subclaim dimension by dimension.
A stance of "supports" means the source entails the complete proposition.
A stance of "contradicts" means the source conflicts with the subclaim on at least one dimension.
A stance of "context" or "neutral" means the source is topically related but not probative.

Rules:
1. Judge only from the supplied evidence. Never use outside knowledge.
2. A subclaim is "supported" only when the supporting evidence entails the complete
   proposition and no contradicting evidence was found.
3. Weigh evidence by independent source group, not by how many articles were retrieved.
4. If there is no probative evidence at all, the answer is "insufficient_evidence".
5. If the evidence conflicts, the answer is "disputed".
6. If the claim is partly supported but an important qualifier is missing, the answer is
   "misleading_or_incomplete".

Return JSON only, with exactly these keys:
  "verdict": one of "supported", "partially_supported", "disputed",
             "misleading_or_incomplete", "unverifiable", "insufficient_evidence"
  "confidence": a number between 0 and 1
  "rationale": two or three sentences explaining the verdict
  "primary_evidence_status": "found", "not_found", "search_failed", or "not_searched\""""


class VerificationSchema(BaseModel):
    verdict: str = VerificationVerdict.INSUFFICIENT_EVIDENCE.value
    confidence: float = 0.3
    rationale: str = ""
    unresolved_contradictions: list[str] = Field(default_factory=list)
    method: str = "llm_evidence_review"


class VerificationAgent:
    """Produce a verdict from assessed evidence, with deterministic guard rails.

    The model proposes a verdict. It cannot grant support that the assessed
    evidence does not carry, cannot exceed the confidence permitted by the number
    of independent source groups, and cannot ignore a recorded contradiction.
    """

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or LLMClient()

    def verify(
        self,
        subclaim,
        evidence_items: list | None = None,
        completeness_result: dict | None = None,
        primary_status: str = "NOT_FOUND",
        independence_summary: dict | None = None,
    ) -> dict:
        items = list(evidence_items or [])
        completeness = completeness_result or {"completeness_status": "UNKNOWN", "missing_context": []}

        stances = {id(item): normalise_stance(getattr(item, "stance", "unknown")) for item in items}
        supporting = [item for item in items if stances[id(item)] == EvidenceStance.SUPPORTS.value]
        contradicting = [item for item in items if stances[id(item)] == EvidenceStance.CONTRADICTS.value]
        context = [
            item for item in items if stances[id(item)] in {EvidenceStance.CONTEXT.value, EvidenceStance.NEUTRAL.value}
        ]

        independent_groups = self._independent_group_count(independence_summary, supporting, items)
        independent_supporting = self._independent_supporting_count(independence_summary, supporting, items)

        proposal, method = self._propose(subclaim, items, stances, completeness, primary_status, independence_summary)

        verdict = proposal["verdict"]
        confidence = float(proposal["confidence"])
        rationale = proposal["rationale"]
        applied_rules: list[str] = []

        # Rule 1: no supporting evidence means the claim is not supported.
        if verdict == VerificationVerdict.SUPPORTED.value and not supporting:
            verdict = (
                VerificationVerdict.DISPUTED.value
                if contradicting
                else VerificationVerdict.INSUFFICIENT_EVIDENCE.value
            )
            applied_rules.append("no_supporting_evidence")
            rationale = (
                rationale
                + " No evidence was assessed as entailing the complete proposition, so support was refused."
            ).strip()

        # Rule 2: contradicting evidence blocks an unqualified supported verdict.
        if contradicting and verdict in {
            VerificationVerdict.SUPPORTED.value,
            VerificationVerdict.PARTIALLY_SUPPORTED.value,
        }:
            verdict = (
                VerificationVerdict.PARTIALLY_SUPPORTED.value if supporting else VerificationVerdict.DISPUTED.value
            )
            applied_rules.append("contradicting_evidence_present")
            rationale = (
                rationale
                + f" {len(contradicting)} evidence item(s) conflict with the subclaim on at least one dimension."
            ).strip()

        # Rule 3: no probative evidence at all cannot yield a positive verdict.
        if not supporting and not contradicting and verdict in {
            VerificationVerdict.SUPPORTED.value,
            VerificationVerdict.PARTIALLY_SUPPORTED.value,
        }:
            verdict = VerificationVerdict.INSUFFICIENT_EVIDENCE.value
            applied_rules.append("no_probative_evidence")
            rationale = (
                rationale
                + " The retrieved documents were topically related but did not address the proposition."
            ).strip()

        # Rule 4: single-group support cannot be reported as fully supported.
        if verdict == VerificationVerdict.SUPPORTED.value and independent_supporting <= 1 and independent_groups <= 1:
            verdict = VerificationVerdict.PARTIALLY_SUPPORTED.value
            applied_rules.append("single_independent_source")
            rationale = (
                rationale
                + " The support rests on a single independent source group, which is reported as partial."
            ).strip()

        # Rule 5: completeness can downgrade but never upgrade a verdict.
        if completeness.get("completeness_status") in {"MISLEADING_BY_OMISSION", "INCOMPLETE"} and supporting:
            if verdict in {VerificationVerdict.SUPPORTED.value, VerificationVerdict.PARTIALLY_SUPPORTED.value}:
                verdict = VerificationVerdict.MISLEADING_OR_INCOMPLETE.value
                applied_rules.append("misleading_by_omission")
                rationale = (
                    rationale + " The claim also omits context needed to interpret it correctly."
                ).strip()

        # Rule 6: confidence is capped by independence, and by raw counts.
        ceiling = _independence_ceiling(independent_supporting if supporting else independent_groups)
        if confidence > ceiling:
            confidence = ceiling
            applied_rules.append("confidence_capped_by_independence")
        if verdict in {
            VerificationVerdict.INSUFFICIENT_EVIDENCE.value,
            VerificationVerdict.UNVERIFIABLE.value,
        }:
            confidence = min(confidence, 0.45)
        confidence = max(0.05, min(0.95, confidence))

        if primary_status == "FOUND" and supporting:
            confidence = min(0.95, confidence + 0.05)
        elif primary_status == "SEARCH_FAILED" and supporting:
            confidence = max(0.1, confidence - 0.05)

        return {
            "subclaim_id": getattr(subclaim, "id", None),
            "subclaim_text": getattr(subclaim, "text", None),
            "verdict": verdict,
            "confidence": round(confidence, 2),
            "rationale": rationale,
            "supporting_evidence_count": len(supporting),
            "contradicting_evidence_count": len(contradicting),
            "context_evidence_count": len(context),
            "independent_supporting_groups": independent_supporting,
            "independent_groups": independent_groups,
            "primary_evidence_status": primary_status,
            "method": method,
            "applied_rules": applied_rules,
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _independent_group_count(independence_summary: dict | None, supporting: list, items: list) -> int:
        if not independence_summary:
            return 0
        total = independence_summary.get("independent_groups", independence_summary.get("evidence_clusters", 0))
        try:
            return int(total)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _independent_supporting_count(independence_summary: dict | None, supporting: list, items: list) -> int:
        group_for_evidence = (independence_summary or {}).get("group_for_evidence") or {}
        if group_for_evidence:
            # Group keys arrive as strings once the summary has been serialised to
            # JSON, and as ints while it is still in memory, so both are accepted.
            groups = set()
            for item in supporting:
                key = getattr(item, "id", None) or id(item)
                group = group_for_evidence.get(key, group_for_evidence.get(str(key)))
                if group is not None:
                    groups.add(group)
            return len(groups)
        if not supporting:
            return 0
        if not independence_summary:
            return 1
        return VerificationAgent._independent_group_count(independence_summary, supporting, items)

    def _propose(
        self,
        subclaim,
        items: list,
        stances: dict[int, str],
        completeness: dict,
        primary_status: str,
        independence_summary: dict | None,
    ) -> tuple[dict[str, Any], str]:
        if not items:
            return {
                "verdict": VerificationVerdict.INSUFFICIENT_EVIDENCE.value,
                "confidence": 0.2,
                "rationale": "No documents were retrieved for this subclaim, so it cannot be assessed.",
            }, "no_evidence"

        try:
            evidence_text = "\n".join(
                f"- [{stances[id(item)]}] {getattr(item, 'summary', '') or ''}".strip()
                for item in items[:20]
            )
            response = self.llm.generate_structured(
                VerificationSchema,
                f"SUBCLAIM:\n{getattr(subclaim, 'text', str(subclaim))}\n\n"
                f"EVIDENCE:\n{evidence_text}\n\n"
                f"COMPLETENESS:\n{completeness}\n\n"
                f"PRIMARY_EVIDENCE_STATUS: {primary_status}\n\n"
                f"INDEPENDENCE: {independence_summary or {}}",
                system_prompt=_VERDICT_INSTRUCTION,
            )
            payload = response.model_dump()
            verdict = str(payload.get("verdict") or VerificationVerdict.INSUFFICIENT_EVIDENCE.value).strip().lower()
            allowed = {member.value for member in VerificationVerdict}
            if verdict not in allowed:
                verdict = VerificationVerdict.INSUFFICIENT_EVIDENCE.value
            return {
                "verdict": verdict,
                "confidence": float(payload.get("confidence", 0.3)),
                "rationale": str(payload.get("rationale") or ""),
            }, "llm_evidence_review"
        except LLMUnavailableError as exc:
            logger.info("Verification model unavailable (%s); using deterministic aggregation.", exc)
        except Exception as exc:  # noqa: BLE001 - fall back rather than fail the investigation
            logger.warning("Verification proposal failed: %s", exc)

        return self._deterministic_proposal(items, stances), "heuristic_evidence_review"

    @staticmethod
    def _deterministic_proposal(items: list, stances: dict[int, str]) -> dict[str, Any]:
        supporting = sum(1 for stance in stances.values() if stance == EvidenceStance.SUPPORTS.value)
        contradicting = sum(1 for stance in stances.values() if stance == EvidenceStance.CONTRADICTS.value)

        if supporting == 0 and contradicting == 0:
            verdict = VerificationVerdict.INSUFFICIENT_EVIDENCE.value
            confidence = 0.25
            rationale = "No retrieved document entailed or conflicted with the complete proposition."
        elif contradicting and not supporting:
            verdict = VerificationVerdict.DISPUTED.value
            confidence = 0.6
            rationale = "The retrieved evidence conflicts with the subclaim and none of it supports it."
        elif contradicting and supporting:
            verdict = VerificationVerdict.PARTIALLY_SUPPORTED.value
            confidence = 0.55
            rationale = "The evidence both supports and conflicts with the subclaim."
        else:
            verdict = VerificationVerdict.SUPPORTED.value
            confidence = 0.65
            rationale = "The retrieved evidence entails the subclaim with no recorded conflict."
        return {"verdict": verdict, "confidence": confidence, "rationale": rationale}
