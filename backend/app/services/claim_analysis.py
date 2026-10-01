from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models import Claim, ClaimStatus, Subclaim, SubclaimType
from app.services.llm import LLMClient, LLMUnavailableError

logger = logging.getLogger(__name__)

class SubclaimListSchema(BaseModel):
    subclaims: list[str] = Field(default_factory=list)


_DECOMPOSE_INSTRUCTION = """Break a news claim into independently checkable subclaims.

Each subclaim must assert exactly one proposition, stated as a complete sentence that
names who or what did what, to whom or where, and when and how much where relevant.
Keep every number, date, place, and qualifier from the original claim in the subclaim
that carries it. Do not add facts that are not in the claim.

Return JSON with a "subclaims" list of strings, using only the supplied claim text."""


class ClaimAnalyzer:
    """Break a claim into independently checkable subclaims."""

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or LLMClient()

    def analyze(self, claim_text: str) -> list[str]:
        cleaned = (claim_text or "").strip()
        if not cleaned:
            raise ValueError("claim_text cannot be empty")

        try:
            response = self.llm.generate_structured(
                SubclaimListSchema,
                f"CLAIM:\n{cleaned}",
                system_prompt=_DECOMPOSE_INSTRUCTION,
            )
            values = response.subclaims
            if isinstance(values, list) and values and all(isinstance(item, str) for item in values):
                decomposed = [item.strip() for item in values if item and item.strip()]
                if decomposed:
                    return decomposed
        except LLMUnavailableError as exc:
            logger.info("Claim decomposition fell back to sentence splitting: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Claim decomposition failed: %s", exc)

        return self._split_on_connectives(cleaned)

    @staticmethod
    def _split_on_connectives(cleaned: str) -> list[str]:
        parts = re.split(r"(?<!\w)and(?!\w)|\s+but\s+|\s+while\s+|\s+although\s+|\s+whereas\s+|;", cleaned)
        segments = [segment.strip(" ,.") for segment in parts if segment and segment.strip(" ,.")]
        if not segments:
            return [cleaned]
        return segments

    def build_claim_record(self, claim_text: str) -> tuple[Claim, list[Subclaim]]:
        claim = Claim(
            claim_text=claim_text,
            normalized_claim=claim_text.strip(),
            status=ClaimStatus.ANALYZING.value,
        )
        subclaims: list[Subclaim] = []
        for index, segment in enumerate(self.analyze(claim_text), start=1):
            subclaims.append(
                Subclaim(
                    claim=claim,
                    text=segment,
                    normalized_text=segment.strip(),
                    subclaim_type=self._infer_subclaim_type(segment).value,
                    priority=index,
                )
            )
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
        """Classify a subclaim by the linguistic shape of the assertion."""
        lower = segment.lower()
        if re.search(r"\b(because|caused|causes|led to|leads to|resulted in|results in|due to|triggered|drove)\b", lower):
            return SubclaimType.CAUSAL
        if re.search(r"\b(forecast|predicts?|projects?|expects?|estimated to|will|is expected to)\b", lower):
            return SubclaimType.PREDICTION
        if re.search(r"\b(opinion|believes|thinks|feels|argues|contends)\b", lower):
            return SubclaimType.OPINION
        if re.search(r"\b(according to|said|stated|claimed|announced|reported|attributed to|blamed|alleged)\b", lower):
            return SubclaimType.ATTRIBUTION
        if re.search(r"\b(vs\.?|versus|compared (to|with)|higher than|lower than|more than|less than|than)\b", lower):
            return SubclaimType.COMPARATIVE
        if re.search(r"(?:\d[\d,.]*\s?(?:%|percent|million|billion|trillion|thousand)\b)|(?:\b\d[\d,.]*%)|\b(?:in|during|by|since|before|after|until)\s+(?:19|20)\d{2}\b", lower):
            if re.search(r"\b(in|during|by|since|before|after|until)\s+(?:19|20)\d{2}\b", lower):
                return SubclaimType.TEMPORAL
            return SubclaimType.QUANTITATIVE
        if re.search(r"\b(before|after|since|until|during|when)\b", lower):
            return SubclaimType.TEMPORAL
        return SubclaimType.FACTUAL
