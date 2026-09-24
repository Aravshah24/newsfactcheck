from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Claim, ClaimStatus, Subclaim, SubclaimType
from app.services.llm import LLMClient


class ClaimBreakdownSchema(BaseModel):
    subclaims: list[str] = Field(default_factory=list)


class ClaimAnalyzer:
    """Break a claim into independently checkable subclaims."""

    def analyze(self, claim_text: str) -> list[str]:
        cleaned = (claim_text or "").strip()
        if not cleaned:
            raise ValueError("claim_text cannot be empty")

        try:
            result = LLMClient().generate_structured(
                ClaimBreakdownSchema,
                f"Decompose this claim into independent checkable subclaims. Keep each subclaim short, factual, and evidence-testable.\n\nCLAIM:\n{cleaned}",
                system_prompt="You are breaking a news claim into independently verifiable subclaims. Return JSON with a 'subclaims' list only. Use only the supplied claim text as context. Do not use outside knowledge.",
            )
            values = getattr(result, "subclaims", None) or getattr(result, "model_dump", lambda: {})().get("subclaims", [])
            if isinstance(values, list) and values and all(isinstance(item, str) for item in values):
                return [item.strip() for item in values if item and item.strip()]
        except Exception:
            pass

        if any(token in cleaned.lower() for token in [" and ", " but ", " while ", ";", ", and "]):
            sentence_parts = re.split(r"(?<!\w)and(?!\w)|\s+but\s+|\s+while\s+|;|\.|\?", cleaned)
        else:
            sentence_parts = [cleaned]

        segments = [segment.strip() for segment in sentence_parts if segment and segment.strip()]
        if not segments:
            segments = [cleaned]
        return segments

    def build_claim_record(self, claim_text: str) -> tuple[Claim, list[Subclaim]]:
        claim = Claim(
            claim_text=claim_text,
            normalized_claim=claim_text.strip(),
            status=ClaimStatus.ANALYZING.value,
        )
        subclaims: list[Subclaim] = []
        for index, segment in enumerate(self.analyze(claim_text), start=1):
            subclaim = Subclaim(
                claim=claim,
                text=segment,
                normalized_text=segment.strip(),
                subclaim_type=self._infer_subclaim_type(segment).value,
                priority=index,
            )
            subclaims.append(subclaim)
        return claim, subclaims

    def persist_claim(self, db: Session, claim_text: str) -> Claim:
        claim, subclaims = self.build_claim_record(claim_text)
        db.add(claim)
        db.flush()
        for subclaim in subclaims:
            db.add(subclaim)
        db.flush()
        claim.status = ClaimStatus.ANALYZING.value
        return claim

    @staticmethod
    def _infer_subclaim_type(segment: str) -> SubclaimType:
        lower = segment.lower()
        if re.search(r"(because|caused|led to|resulted in|due to|triggered)", lower):
            return SubclaimType.CAUSAL
        if re.search(r"(before|after|since|until|during|in 20\d\d|by 20\d\d|in 202[0-9])", lower):
            return SubclaimType.TEMPORAL
        if re.search(r"(\b\d+\b|\d+%|%|million|billion|average|total|more than|less than|at least|up to|increase|decrease)", lower):
            return SubclaimType.QUANTITATIVE
        if re.search(r"(vs\.|versus|compared|higher than|lower than|more than|less than)", lower):
            return SubclaimType.COMPARATIVE
        if re.search(r"(according to|said|claimed|announced|reported by|attributed to|blamed)", lower):
            return SubclaimType.ATTRIBUTION
        if re.search(r"(will|forecast|expected|likely|predicted|could|may|should)", lower):
            return SubclaimType.PREDICTION
        if re.search(r"(opinion|believes|thinks|feels|should|seems)", lower):
            return SubclaimType.OPINION
        return SubclaimType.FACTUAL
