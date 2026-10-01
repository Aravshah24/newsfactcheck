from __future__ import annotations

import logging
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.services.llm import LLMClient, LLMUnavailableError

logger = logging.getLogger(__name__)

DimensionStatus = Literal["match", "conflict", "absent", "not_specified", "unclear"]

# The dimensions a proposition is compared along. These are generic linguistic
# roles, deliberately independent of any domain, entity, or event type.
DIMENSIONS: tuple[str, ...] = (
    "subject",
    "action",
    "object",
    "date_time",
    "quantity",
    "polarity",
    "qualifiers",
)

# Dimensions that must be resolved for evidence to count as entailing the claim.
# The remaining dimensions may legitimately be absent from a given document.
REQUIRED_FOR_SUPPORT: tuple[str, ...] = ("subject", "action")

_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_FULL_DATE_RE = re.compile(
    r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+\d{1,2}(?:,\s*\d{4})?\b",
    re.IGNORECASE,
)
_QUANTITY_RE = re.compile(
    r"(?:[$€£]\s?\d[\d,.]*|\b\d[\d,.]*\s?(?:percent|percentage points?|pp|billion|million|trillion|thousand)\b|\b\d[\d,.]*%|\b\d[\d,.]*\s?(?:units?|people|cases|deaths|jobs|votes|tonnes?|tons?|kg|km|miles?|barrels?)\b)",
    re.IGNORECASE,
)
_NEGATION_RE = re.compile(
    r"\b(?:not|never|no|none|nothing|nobody|cannot|can't|won't|wouldn't|didn't|doesn't|isn't|wasn't|"
    r"aren't|weren't|hasn't|haven't|hadn't|fails? to|failed to|without)\b",
    re.IGNORECASE,
)
_QUALIFIER_RE = re.compile(
    r"\b(?:only|just|almost|nearly|approximately|roughly|some|many|most|all|at least|up to|"
    r"as much as|partially|partly|possibly|perhaps|allegedly|reportedly|temporarily|"
    r"in some cases|for now|initially|eventually|so far)\b",
    re.IGNORECASE,
)


class PropositionDimension(BaseModel):
    dimension: str
    value: str = ""
    status: DimensionStatus = "unclear"
    conflict: str = ""
    evidence_value: str = ""
    note: str = ""


class PropositionSchema(BaseModel):
    """Structured decomposition of a claim into comparable dimensions."""

    subject: str = ""
    action: str = ""
    object: str = ""
    date_time: str = ""
    quantity: str = ""
    polarity: str = "affirmative"
    qualifiers: list[str] = Field(default_factory=list)
    is_atomic: bool = True
    notes: str = ""


class BatchedPropositionItem(PropositionSchema):
    index: int = 0


class BatchedPropositionSchema(BaseModel):
    items: list[BatchedPropositionItem] = Field(default_factory=list)


def proposition_schema_instruction() -> str:
    lines = [
        "Return JSON only, with exactly these keys:",
        '  "subject": the specific entity or entities the statement is about.',
        '  "action": the event, predicate, or relation asserted.',
        '  "object": the object, location, target, or complement of the action.',
        '  "date_time": any explicit date, year, or time reference, else "".',
        '  "quantity": any explicit number with its unit, else "".',
        '  "polarity": "affirmative" if the statement asserts something happened,',
        '                "negative" if it asserts that something did not happen.',
        '  "qualifiers": list of scoping words that limit the statement (scope, exceptions, hedges).',
        '  "is_atomic": true if the statement asserts exactly one checkable proposition, else false.',
        '  "notes": short free-text note, may be "".',
        "Use the exact wording of the statement. Do not add outside knowledge, and do not",
        "invent a value for a dimension the statement does not specify; use an empty string.",
        "When several statements are supplied at once, return them in an \"items\" list where",
        "each item repeats every key above and also carries an \"index\" integer identifying",
        "which statement it decomposes.",
    ]
    return "\n".join(lines)


class Proposition:
    """A claim expressed as comparable dimensions plus a degradation flag.

    ``degraded`` is True when the structured decomposition could not be obtained
    from the LLM. Callers must not treat a degraded proposition as evidence that
    a document entails the claim.
    """

    def __init__(
        self,
        text: str,
        dimensions: dict[str, Any],
        degraded: bool = False,
        notes: str = "",
        is_atomic: bool = True,
    ):
        self.text = text
        self.degraded = degraded
        self.notes = notes
        self.is_atomic = is_atomic
        self.dimensions: dict[str, str] = {
            key: (str(dimensions.get(key) or "").strip() if key != "qualifiers" else list(dimensions.get(key) or []))
            for key in DIMENSIONS
        }

    def value(self, dimension: str) -> Any:
        return self.dimensions.get(dimension, "")

    def specified(self) -> list[str]:
        return [name for name in DIMENSIONS if self.dimensions.get(name)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "degraded": self.degraded,
            "is_atomic": self.is_atomic,
            "notes": self.notes,
            "dimensions": {name: self.dimensions.get(name) for name in DIMENSIONS},
        }

    def prompt_block(self) -> str:
        rows = []
        for name in DIMENSIONS:
            value = self.dimensions.get(name)
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value) if value else ""
            rows.append(f"  {name}: {value if value else '(not specified)'}")
        return "\n".join(rows)


class PropositionExtractor:
    """Decompose a claim into comparable dimensions.

    This is a general linguistic decomposition. It contains no domain, entity,
    or event specific rules; the dimension semantics come from the prompt and
    from generic surface-form cues (dates, quantities, negation, hedges).
    """

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or LLMClient()

    def extract(self, claim_text: str) -> Proposition:
        return self.extract_many([claim_text])[0]

    def extract_many(self, claim_texts: list[str]) -> list[Proposition]:
        """Decompose several statements in a single model call.

        Providers meter per request, so batching keeps claim decomposition to one
        call per investigation instead of one per subclaim.
        """
        texts = [(text or "").strip() for text in claim_texts]
        if not texts:
            return []
        if len(texts) == 1:
            return [self._extract_one(texts[0])]
        try:
            return self._extract_batch(texts)
        except LLMUnavailableError as exc:
            logger.info("Batched proposition extraction unavailable (%s); per-statement fallback.", exc)
        except Exception as exc:  # noqa: BLE001 - never let decomposition break the pipeline
            logger.warning("Batched proposition extraction failed: %s", exc)
        return [self._extract_one(text) for text in texts]

    def _extract_batch(self, texts: list[str]) -> list[Proposition]:
        listing = "\n\n".join(f"STATEMENT {index}:\n{text}" for index, text in enumerate(texts))
        schema = self.llm.generate_structured(
            BatchedPropositionSchema,
            f"Decompose each statement into its comparable dimensions.\n\n{listing}",
            system_prompt=(
                "You decompose statements into comparable dimensions. "
                + proposition_schema_instruction()
            ),
        )
        by_index = {item.index: item for item in (schema.items or [])}
        results: list[Proposition] = []
        for index, text in enumerate(texts):
            item = by_index.get(index)
            if item is None:
                results.append(self._fallback(text))
                continue
            payload = item.model_dump()
            results.append(self._build(text, payload, degraded=False))
        return results

    def _build(self, text: str, payload: dict, degraded: bool, notes: str = "") -> Proposition:
        return Proposition(
            text=text,
            dimensions={
                "subject": payload.get("subject", ""),
                "action": payload.get("action", ""),
                "object": payload.get("object", ""),
                "date_time": payload.get("date_time", ""),
                "quantity": payload.get("quantity", ""),
                "polarity": payload.get("polarity", "affirmative"),
                "qualifiers": payload.get("qualifiers", []),
            },
            degraded=degraded,
            notes=notes or payload.get("notes", ""),
            is_atomic=bool(payload.get("is_atomic", True)),
        )

    def _extract_one(self, text: str) -> Proposition:
        if not text:
            return Proposition(text, {}, degraded=True, notes="Empty claim text.")

        try:
            schema = self.llm.generate_structured(
                PropositionSchema,
                f"Decompose this single statement into its comparable dimensions.\n\n"
                f"STATEMENT:\n{text}",
                system_prompt=(
                    "You decompose statements into comparable dimensions. "
                    + proposition_schema_instruction()
                ),
            )
            return self._build(text, schema.model_dump(), degraded=False)
        except LLMUnavailableError as exc:
            logger.info("Falling back to surface-form proposition extraction: %s", exc)
            return self._fallback(text)
        except Exception as exc:  # noqa: BLE001 - never let decomposition break the pipeline
            logger.warning("Proposition extraction failed for %r: %s", text, exc)
            return self._fallback(text)

    @staticmethod
    def _fallback(text: str) -> Proposition:
        """Generic surface-form extraction.

        Only cues that are unambiguous without world knowledge are used: explicit
        dates, explicit quantities, negation, and hedging qualifiers. Subject,
        action, and object are left empty because they cannot be recovered
        reliably without a parser, and the result is marked degraded.
        """
        dates = _FULL_DATE_RE.findall(text)
        years = _YEAR_PATTERN_SAFE(text)
        date_time = ", ".join(dates + years) if (dates or years) else ""
        quantities = _QUANTITY_RE.findall(text)
        quantity = ", ".join(q.strip() for q in quantities) if quantities else ""
        polarity = "negative" if _NEGATION_RE.search(text) else "affirmative"
        qualifiers = sorted({match.group(0).lower() for match in _QUALIFIER_RE.finditer(text)})
        return Proposition(
            text=text,
            dimensions={
                "subject": "",
                "action": "",
                "object": "",
                "date_time": date_time,
                "quantity": quantity,
                "polarity": polarity,
                "qualifiers": qualifiers,
            },
            degraded=True,
            notes="Surface-form only: subject, action, and object were not resolved.",
        )


def _YEAR_PATTERN_SAFE(text: str) -> list[str]:
    seen: list[str] = []
    for match in _YEAR_RE.findall(text):
        if match not in seen:
            seen.append(match)
    return seen
