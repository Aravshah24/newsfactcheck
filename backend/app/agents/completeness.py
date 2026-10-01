from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

from app.services.llm import LLMClient, LLMUnavailableError

logger = logging.getLogger(__name__)

_COMPLETENESS_INSTRUCTION = """Judge whether a claim is technically accurate but incomplete or misleading.

Look for:
  - a missing baseline, comparison period, or denominator for a number
  - a missing time frame, or a time frame that is ambiguous
  - an omitted exception, carve-out, or population restriction
  - causal language that is asserted without evidence of causation
  - an omitted population, jurisdiction, or scope limit
  - a qualifier the reader would need in order to interpret the claim correctly

Use only the supplied claim, subclaims, and evidence. Do not use outside knowledge.
If the claim is adequately qualified, return an empty "missing_context" list.

Return JSON with:
  "completeness_status": one of "COMPLETE", "MOSTLY_COMPLETE", "INCOMPLETE", "MISLEADING_BY_OMISSION"
  "missing_context": list of specific missing elements
  "qualifications": list of qualifications a reader needs
  "explanation": one or two sentences
  "confidence": a number between 0 and 1"""


class CompletenessSchema(BaseModel):
    completeness_status: str = "MOSTLY_COMPLETE"
    missing_context: list[str] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list)
    explanation: str = ""
    confidence: float = 0.6


_VALID_STATUSES = {"COMPLETE", "MOSTLY_COMPLETE", "INCOMPLETE", "MISLEADING_BY_OMISSION"}


class CompletenessAgent:
    """Detect whether a claim may be true but incomplete or misleading by omission."""

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or LLMClient()

    def analyze(self, claim_text: str, evidence_items: list | None = None, subclaims: list | None = None) -> dict:
        claim = (claim_text or "").strip()
        items = list(evidence_items or [])

        try:
            evidence_summary = "\n".join(f"- {getattr(item, 'summary', str(item))}" for item in items[:10]) or (
                "No direct evidence was retrieved."
            )
            subclaim_summary = "\n".join(f"- {getattr(item, 'text', str(item))}" for item in (subclaims or [])[:10]) or (
                "No decomposed subclaims provided."
            )
            response = self.llm.generate_structured(
                CompletenessSchema,
                f"CLAIM:\n{claim}\n\nSUBCLAIMS:\n{subclaim_summary}\n\nEVIDENCE:\n{evidence_summary}",
                system_prompt=_COMPLETENESS_INSTRUCTION,
            )
            values = response.model_dump()
            status = str(values.get("completeness_status", "MOSTLY_COMPLETE")).strip().upper()
            if status not in _VALID_STATUSES:
                status = "MOSTLY_COMPLETE"
            return {
                "completeness_status": status,
                "missing_context": list(values.get("missing_context") or []),
                "qualifications": list(values.get("qualifications") or []),
                "explanation": str(values.get("explanation") or ""),
                "confidence": max(0.0, min(1.0, float(values.get("confidence", 0.6)))),
            }
        except LLMUnavailableError as exc:
            logger.info("Completeness analysis fell back to structural checks: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Completeness analysis failed: %s", exc)

        return self._structural_fallback(claim, items)

    @staticmethod
    def _structural_fallback(claim: str, items: list) -> dict:
        missing_context: list[str] = []
        qualifications: list[str] = []
        lower = claim.lower()

        if re.search(r"\b(caused|causes|led to|resulted in|because|due to|drove)\b", lower) and not re.search(
            r"\b(before|after|while|compared|without|except|only|relative to|than)\b", lower
        ):
            missing_context.append("A causal claim is made without an explicit comparison or baseline.")
            qualifications.append("Causation should be treated cautiously unless the causal comparison is demonstrated.")

        if re.search(r"(\d+\s?%|\bincrease|\bdecrease|\bdrop|\brise|\bgrowth|\bgain|\bfall)", lower) and not re.search(
            r"\b(compared to|relative to|before|after|from|to|baseline|versus|since)\b", lower
        ):
            missing_context.append("A numeric change is reported without a baseline, comparison period, or qualifier.")
            qualifications.append("Percent change requires the relevant baseline or prior period for interpretation.")

        if re.search(r"\b(after|before|since|until)\b", lower) and not re.search(
            r"\b(after|before|since|until|during|in)\s+((19|20)\d{2}|\d{1,2}\s+\w+)", lower
        ):
            missing_context.append("The temporal framing may be incomplete or ambiguous.")
            qualifications.append("The relevant period or timing should be stated explicitly.")

        if not items:
            missing_context.append("No evidence was retrieved during this investigation.")
            qualifications.append("The claim remains unsupported until additional sources are checked.")

        if not missing_context:
            status, confidence = "COMPLETE", 0.6
        elif len(missing_context) >= 2:
            status, confidence = "MISLEADING_BY_OMISSION", 0.7
        else:
            status, confidence = "MOSTLY_COMPLETE", 0.55

        explanation = (
            "The claim may be incomplete or misleading because relevant context, a time baseline, or a qualifier is missing."
            if missing_context
            else "The claim was reviewed for missing context, unsupported inference, and qualifier gaps."
        )
        return {
            "completeness_status": status,
            "missing_context": missing_context,
            "qualifications": qualifications,
            "explanation": explanation,
            "confidence": round(confidence, 2),
        }
