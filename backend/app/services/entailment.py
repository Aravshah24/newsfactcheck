from __future__ import annotations

import logging
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import settings
from app.services.llm import LLMClient, LLMUnavailableError
from app.services.proposition import DIMENSIONS, Proposition, PropositionExtractor

logger = logging.getLogger(__name__)

DimensionStatus = Literal["match", "conflict", "absent", "unclear"]

_ENTAILMENT_INSTRUCTION = """You compare one or more claims against a single source document, dimension by dimension.

Each claim is already decomposed. For EACH claim, and for EACH of its dimensions, decide:
  - "match"    the document states the same value as the claim for that dimension
  - "conflict" the document states a DIFFERENT value for that dimension than the claim
  - "absent"   the document does not state this dimension at all
  - "unclear"  the document touches the dimension but is too vague to compare

Rules you must follow:
1. A document only SUPPORTS a claim if EVERY dimension the claim specifies is "match",
   and every dimension the document states is compatible with the claim.
2. Any single "conflict" on any dimension makes that document CONTRADICTS the claim. This
   includes a different subject, a different action, a different object or location, a
   different date or year, a different quantity, opposite polarity, or a qualifier that
   limits the claim's scope.
3. A document that is about the same topic, shares the subject, or merely repeats some
   wording is CONTEXT. Sharing a subject is not support. Mentioning an event at all is
   not support. If the document does not address the specific proposition, it is CONTEXT.
4. If the document is entirely unrelated to a claim, use stance "neutral" for that claim.
5. Judge each claim independently. The same document may support one claim, contradict
   another, and be neutral on a third.
6. Never use outside knowledge. Only the supplied claims and document text.
7. Be strict: when uncertain between "match" and "absent", choose "absent".

Return JSON only, with exactly these keys:
  "results": a list with one object per (claim, document) pair.
    Each object has:
      "claim_index": the integer index of the claim being judged
      "document_index": the integer index of the document being judged
      "stance": one of "supports", "contradicts", "context", "neutral"
      "dimensions": a list with one object per dimension, each having
          "dimension": one of """ + ", ".join(DIMENSIONS) + """
          "status":   one of "match", "conflict", "absent", "unclear"
          "evidence_value": the value the document states for that dimension, or ""
          "note": a short explanation of any conflict, or ""
      "confidence": a number between 0 and 1
      "rationale": one or two sentences naming the decisive dimension

You must return exactly one result for every (claim, document) pair. Do not skip any."""


class DimensionComparison(BaseModel):
    dimension: str
    status: DimensionStatus = "absent"
    evidence_value: str = ""
    note: str = ""


class EntailmentSchema(BaseModel):
    stance: str = "context"
    dimensions: list[DimensionComparison] = Field(default_factory=list)
    confidence: float = 0.3
    rationale: str = ""


class BatchedEntailmentItem(BaseModel):
    claim_index: int = 0
    stance: str = "context"
    dimensions: list[DimensionComparison] = Field(default_factory=list)
    confidence: float = 0.3
    rationale: str = ""


class BatchedEntailmentSchema(BaseModel):
    results: list[BatchedEntailmentItem] = Field(default_factory=list)


class MultiDocumentEntailmentItem(BatchedEntailmentItem):
    document_index: int = 0


class MultiDocumentEntailmentSchema(BaseModel):
    results: list[MultiDocumentEntailmentItem] = Field(default_factory=list)


class EntailmentResult:
    """Outcome of comparing one proposition against one document."""

    def __init__(
        self,
        stance: str,
        confidence: float,
        rationale: str,
        dimension_status: dict[str, str],
        dimension_conflicts: dict[str, str],
        method: str,
    ):
        self.stance = stance
        self.confidence = confidence
        self.rationale = rationale
        self.dimension_status = dimension_status
        self.dimension_conflicts = dimension_conflicts
        self.method = method

    def to_dict(self) -> dict[str, Any]:
        return {
            "stance": self.stance,
            "confidence": round(self.confidence, 3),
            "rationale": self.rationale,
            "dimension_status": self.dimension_status,
            "dimension_conflicts": self.dimension_conflicts,
            "method": self.method,
        }


_STANCE_VALUES = {"supports", "contradicts", "context", "neutral", "unknown"}


class EntailmentEngine:
    """Decide whether a document entails, contradicts, or merely contextualises a claim.

    The engine is domain-agnostic. All proposition-level semantics come from the
    structured decomposition of the claim and from the per-dimension comparison the
    model returns. No entity, event, or location rules are encoded here.
    """

    def __init__(self, llm: LLMClient | None = None, extractor: PropositionExtractor | None = None):
        self.llm = llm or LLMClient()
        self.extractor = extractor or PropositionExtractor(llm=self.llm)
        self._proposition_cache: dict[str, Proposition] = {}

    def proposition_for(self, claim_text: str) -> Proposition:
        key = (claim_text or "").strip()
        cached = self._proposition_cache.get(key)
        if cached is None:
            cached = self.extractor.extract(key)
            self._proposition_cache[key] = cached
        return cached

    def preload_propositions(self, claim_texts: list[str]) -> dict[str, Proposition]:
        """Decompose every subclaim in one model call and cache the results."""
        missing = [text for text in claim_texts if (text or "").strip() not in self._proposition_cache]
        if missing:
            for text, proposition in zip(missing, self.extractor.extract_many(missing)):
                self._proposition_cache[(text or "").strip()] = proposition
        return dict(self._proposition_cache)

    def assess(self, proposition: Proposition, evidence_text: str, document_title: str = "") -> EntailmentResult:
        return self.assess_many([proposition], evidence_text, document_title)[0]

    def assess_documents(
        self,
        propositions: list[Proposition],
        documents: list[tuple[str, str]],
    ) -> list[list[EntailmentResult]]:
        """Assess several documents against several claims, grouped per document.

        Providers meter per request, so grouping documents keeps an investigation
        inside a realistic budget. The result is one entry per document, each
        holding one :class:`EntailmentResult` per claim, in input order.
        """
        if not documents:
            return []
        if not propositions:
            return [[] for _ in documents]

        prepared: list[tuple[str, str]] = []
        for title, text in documents:
            clean_text = (text or "").strip()
            prepared.append(((title or "").strip(), clean_text))

        group_size = max(1, int(settings.EVIDENCE_DOCUMENT_BATCH_SIZE))
        out: list[list[EntailmentResult]] = []
        for start in range(0, len(prepared), group_size):
            group = prepared[start : start + group_size]
            out.extend(self._assess_group(list(propositions), group))
        return out

    def _assess_group(
        self, propositions: list[Proposition], group: list[tuple[str, str]]
    ) -> list[list[EntailmentResult]]:
        usable = [(title, text) for title, text in group if text or title]
        if not usable:
            return [
                [self._empty_document_result() for _ in propositions]
                for _ in group
            ]

        try:
            schema = self.llm.generate_structured(
                MultiDocumentEntailmentSchema,
                self._build_group_prompt(propositions, usable),
                system_prompt=_ENTAILMENT_INSTRUCTION,
            )
        except LLMUnavailableError as exc:
            logger.info("Entailment model unavailable (%s); using non-probative fallback.", exc)
            fallback = [[self._non_probative_fallback(prop, "llm_unavailable") for prop in propositions] for _ in group]
            return fallback
        except Exception as exc:  # noqa: BLE001 - never let one document break extraction
            logger.warning("Entailment assessment failed: %s", exc)
            return [[self._non_probative_fallback(prop, "assessment_error") for prop in propositions] for _ in group]

        by_pair: dict[tuple[int, int], BatchedEntailmentItem] = {
            (item.document_index, item.claim_index): item for item in (schema.results or [])
        }
        results: list[list[EntailmentResult]] = []
        for document_index in range(len(group)):
            row: list[EntailmentResult] = []
            for claim_index, proposition in enumerate(propositions):
                item = by_pair.get((document_index, claim_index))
                if item is None:
                    # A pair the model omitted is never treated as support.
                    row.append(self._non_probative_fallback(proposition, "pair_omitted_from_response"))
                    continue
                row.append(
                    self._reconcile(
                        proposition,
                        EntailmentSchema(
                            stance=item.stance,
                            dimensions=item.dimensions,
                            confidence=item.confidence,
                            rationale=item.rationale,
                        ),
                    )
                )
            results.append(row)
        return results

    def assess_many(
        self,
        propositions: list[Proposition],
        evidence_text: str,
        document_title: str = "",
    ) -> list[EntailmentResult]:
        """Assess one document against every subclaim in a single model call."""
        if not propositions:
            return []
        rows = self.assess_documents(propositions, [(document_title, evidence_text)])
        return rows[0] if rows else []

    @staticmethod
    def _empty_document_result() -> EntailmentResult:
        return EntailmentResult(
            stance="neutral",
            confidence=0.1,
            rationale="The document contained no extractable text to compare.",
            dimension_status={name: "absent" for name in DIMENSIONS},
            dimension_conflicts={},
            method="empty_document",
        )

    def _build_group_prompt(
        self, propositions: list[Proposition], group: list[tuple[str, str]]
    ) -> str:
        claims = "\n\n".join(
            f"CLAIM {index}:\n  text: {proposition.text}\n{proposition.prompt_block()}"
            for index, proposition in enumerate(propositions)
        )
        limit = max(200, int(settings.EVIDENCE_MAX_EXCERPT_CHARS))
        documents = "\n\n".join(
            f"DOCUMENT {index}:\n  title: {title or '(none)'}\n  text: {text[:limit]}"
            for index, (title, text) in enumerate(group)
        )
        return f"{claims}\n\n{documents}"

    def _reconcile(self, proposition: Proposition, schema: EntailmentSchema) -> EntailmentResult:
        """Apply deterministic guard rails on top of the model's comparison."""
        status: dict[str, str] = {}
        conflicts: dict[str, str] = {}
        for comparison in schema.dimensions or []:
            name = str(comparison.dimension or "").strip()
            if name not in DIMENSIONS:
                continue
            status[name] = str(comparison.status or "absent")
            if status[name] == "conflict":
                conflicts[name] = comparison.evidence_value or comparison.note or "conflicting value"

        model_stance = str(schema.stance or "context").strip().lower()
        if model_stance not in _STANCE_VALUES:
            model_stance = "context"

        specified = set(proposition.specified())

        # Guard rail 1: any reported conflict is a contradiction, whatever the model concluded.
        if conflicts:
            names = ", ".join(sorted(conflicts))
            return EntailmentResult(
                stance="contradicts",
                confidence=max(0.5, min(1.0, float(schema.confidence or 0.5))),
                rationale=f"Conflicting dimension(s): {names}. {schema.rationale}".strip(),
                dimension_status=status,
                dimension_conflicts=conflicts,
                method="llm_dimension_contradiction",
            )

        # Guard rail 2: support requires every specified dimension to be affirmatively matched.
        if model_stance == "supports":
            unspecified_or_unresolved = [
                name for name in sorted(specified) if status.get(name) != "match"
            ]
            if unspecified_or_unresolved:
                return EntailmentResult(
                    stance="context",
                    confidence=0.35,
                    rationale=(
                        f"The document does not establish the claim's "
                        f"{', '.join(unspecified_or_unresolved)} dimension(s), so it does not "
                        "entail the complete proposition."
                    ),
                    dimension_status=status,
                    dimension_conflicts=conflicts,
                    method="llm_support_rejected_incomplete",
                )
            return EntailmentResult(
                stance="supports",
                confidence=max(0.5, min(1.0, float(schema.confidence or 0.5))),
                rationale=schema.rationale or "The document entails every dimension of the claim.",
                dimension_status=status,
                dimension_conflicts=conflicts,
                method="llm_dimension_support",
            )

        if model_stance in {"neutral", "unknown"}:
            return EntailmentResult(
                stance="neutral",
                confidence=max(0.0, min(1.0, float(schema.confidence or 0.0))),
                rationale=schema.rationale or "The document does not address the claim.",
                dimension_status=status,
                dimension_conflicts=conflicts,
                method="llm_dimension_neutral",
            )

        # The model said "context": treat shared topic without full entailment as non-probative.
        return EntailmentResult(
            stance="context",
            confidence=max(0.0, min(1.0, float(schema.confidence or 0.3))),
            rationale=schema.rationale or "The document is related but does not entail the claim.",
            dimension_status=status,
            dimension_conflicts=conflicts,
            method="llm_dimension_context",
        )

    @staticmethod
    def _non_probative_fallback(proposition: Proposition, method: str) -> EntailmentResult:
        """Without a model we cannot establish entailment, so we never assert support.

        A document can still be recorded as contradicting when a generic, high
        precision signal applies, but absence of a model never creates support.
        """
        return EntailmentResult(
            stance="context",
            confidence=0.2,
            rationale=(
                "Propositional comparison was unavailable, so this document is recorded as "
                "context rather than as support."
            ),
            dimension_status={name: "unclear" for name in DIMENSIONS},
            dimension_conflicts={},
            method=method,
        )
