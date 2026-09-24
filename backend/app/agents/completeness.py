from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from app.config import settings
from app.services.llm import LLMClient


class CompletenessSchema(BaseModel):
    completeness_status: str = "MOSTLY_COMPLETE"
    missing_context: list[str] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list)
    explanation: str = ""
    confidence: float = 0.7


class CompletenessAgent:
    """Detect whether a claim may be technically true but incomplete or misleading by omission."""

    def analyze(self, claim_text: str, evidence_items: list | None = None, subclaims: list | None = None) -> dict:
        claim = (claim_text or "").strip()
        try:
            evidence_summary = "\n".join(
                f"- {getattr(item, 'summary', str(item))}" for item in (evidence_items or [])[:10]
            ) or "No direct evidence was retrieved."
            subclaim_summary = "\n".join(
                f"- {getattr(item, 'text', str(item))}" for item in (subclaims or [])[:10]
            ) or "No decomposed subclaims provided."
            response = LLMClient().generate_structured(
                CompletenessSchema,
                f"Assess completeness using only the provided claim, subclaims, and evidence. Do not use outside knowledge.\n\nCLAIM:\n{claim}\n\nSUBCLAIMS:\n{subclaim_summary}\n\nEVIDENCE:\n{evidence_summary}",
                system_prompt="Judge whether the claim is missing material qualifiers, timeframes, scope, counter-evidence, or causal baselines. Return JSON with: completeness_status, missing_context, qualifications, explanation, confidence. Use only the supplied evidence."
            )
            values = response.model_dump() if hasattr(response, "model_dump") else dict(response)
            if isinstance(values, dict) and values:
                normalized = {
                    "completeness_status": str(values.get("completeness_status", "MOSTLY_COMPLETE")).upper(),
                    "missing_context": values.get("missing_context") or [],
                    "qualifications": values.get("qualifications") or [],
                    "explanation": values.get("explanation") or "The claim was reviewed against the supplied evidence and context.",
                    "confidence": float(values.get("confidence", 0.7)),
                }
                return normalized
        except Exception:
            pass

        missing_context: list[str] = []
        qualifications: list[str] = []
        lower = claim.lower()

        if any(token in lower for token in ["caused", "led to", "resulted in", "because", "due to"]):
            if not re.search(r"(before|after|while|compared|without|except|only|relative to)", lower):
                missing_context.append("A causal claim is being made without an explicit comparison or baseline.")
                qualifications.append("Causation should be treated cautiously unless the causal comparison is demonstrated.")

        if re.search(r"(\d+%|%|increase|decrease|drop|rise|growth|gain|fall)", lower) and not re.search(
            r"(compared to|relative to|before|after|from|to|baseline|versus|since)", lower
        ):
            missing_context.append("A numeric change is reported without a baseline, comparison period, or qualifier.")
            qualifications.append("Percent change requires the relevant baseline or prior period for interpretation.")

        if any(token in lower for token in ["after", "before", "since", "until"]) and not re.search(r"(before|after|since|until|during)\s+\d", lower):
            missing_context.append("The temporal framing may be incomplete or ambiguous.")
            qualifications.append("The relevant period or timing should be stated explicitly.")

        if evidence_items is not None and not evidence_items:
            missing_context.append("No direct evidence was retrieved during the local investigation.")
            qualifications.append("The claim remains unsupported until additional sources are checked.")

        if not missing_context:
            status = "COMPLETE"
            confidence = 0.75
        elif len(missing_context) >= 2:
            status = "MISLEADING_BY_OMISSION"
            confidence = 0.78
        else:
            status = "MOSTLY_COMPLETE"
            confidence = 0.62

        explanation = "The claim was reviewed for missing context, unsupported inference, and qualifier gaps."
        if missing_context:
            explanation = "The claim may be incomplete or misleading because the relevant context, time baseline, or qualifier is missing."

        return {
            "completeness_status": status,
            "missing_context": missing_context,
            "qualifications": qualifications,
            "explanation": explanation,
            "confidence": round(confidence, 2),
        }
