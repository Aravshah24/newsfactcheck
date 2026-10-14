from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from app.models import Subclaim
from app.services.claim_analysis import ClaimAnalyzer
from app.services.llm import LLMClient, LLMUnavailableError

logger = logging.getLogger(__name__)


class DecompositionQualitySchema(BaseModel):
    """Quality assessment of a claim decomposition."""

    coverage_score: float = Field(ge=0.0, le=1.0, description="How well the subclaims cover the original claim (0-1)")
    atomicity_score: float = Field(ge=0.0, le=1.0, description="Whether each subclaim is independently checkable (0-1)")
    no_hallucination_score: float = Field(ge=0.0, le=1.0, description="Whether subclaims only contain info from original claim (0-1)")
    overall_quality: float = Field(ge=0.0, le=1.0, description="Weighted overall quality score (0-1)")
    issues: list[str] = Field(default_factory=list, description="Specific issues found")
    recommendations: list[str] = Field(default_factory=list, description="Suggestions for improvement")
    is_acceptable: bool = Field(description="Whether the decomposition passes quality threshold")


_DECOMPOSITION_VALIDATOR_INSTRUCTION = """You are evaluating the quality of a claim decomposition.

Given an ORIGINAL CLAIM and a set of PROPOSED SUBCLAIMS, assess:

1. COVERAGE: Do the subclaims together cover all the factual assertions in the original claim?
   - Every number, date, name, causal claim, and qualifier in the original must appear in at least one subclaim
   - No important factual content should be lost

2. ATOMICITY: Is each subclaim independently checkable?
   - Each subclaim should assert exactly one verifiable proposition
   - Compound statements (joined by "and", "but", "because") should be split
   - A subclaim like "X and Y" is not atomic if X and Y can be independently true/false

3. NO HALLUCINATION: Do the subclaims only contain information from the original claim?
   - No new facts, numbers, entities, or causal links should be introduced
   - Paraphrasing is fine; invention is not

Return JSON with:
- coverage_score (0-1)
- atomicity_score (0-1)
- no_hallucination_score (0-1)
- overall_quality (0-1, weighted average)
- issues (list of specific problems found)
- recommendations (list of suggestions)
- is_acceptable (bool: overall_quality >= 0.7)"""


class DecompositionValidator:
    """Validate the quality of claim decompositions."""

    def __init__(self, llm: LLMClient | None = None, threshold: float = 0.7):
        self.llm = llm or LLMClient()
        self.threshold = threshold

    def validate(self, original_claim: str, subclaims: list[str] | list[Subclaim]) -> dict[str, Any]:
        """Validate a decomposition against the original claim."""
        subclaim_texts = [
            sc.text if isinstance(sc, Subclaim) else str(sc)
            for sc in subclaims
        ]

        if not subclaim_texts:
            return {
                "coverage_score": 0.0,
                "atomicity_score": 0.0,
                "no_hallucination_score": 0.0,
                "overall_quality": 0.0,
                "issues": ["No subclaims produced"],
                "recommendations": ["Decomposition failed to produce any subclaims"],
                "is_acceptable": False,
            }

        # Run LLM-based validation
        try:
            response = self.llm.generate_structured(
                DecompositionQualitySchema,
                f"ORIGINAL CLAIM:\n{original_claim}\n\nPROPOSED SUBCLAIMS:\n"
                + "\n".join(f"- {sc}" for sc in subclaim_texts),
                system_prompt=_DECOMPOSITION_VALIDATOR_INSTRUCTION,
            )
            values = response.model_dump()

            return {
                "coverage_score": float(values.get("coverage_score", 0.0)),
                "atomicity_score": float(values.get("atomicity_score", 0.0)),
                "no_hallucination_score": float(values.get("no_hallucination_score", 0.0)),
                "overall_quality": float(values.get("overall_quality", 0.0)),
                "issues": list(values.get("issues", [])),
                "recommendations": list(values.get("recommendations", [])),
                "is_acceptable": bool(values.get("is_acceptable", False)),
            }
        except LLMUnavailableError as exc:
            logger.info("Decomposition validation fell back to structural checks: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Decomposition validation failed: %s", exc)

        # Fallback: structural checks
        return self._structural_fallback(original_claim, subclaim_texts)

    def _structural_fallback(self, original: str, subclaims: list[str]) -> dict[str, Any]:
        """Basic structural validation when LLM is unavailable."""
        issues = []
        recommendations = []

        # Check 1: Empty or too few subclaims
        if len(subclaims) == 0:
            issues.append("No subclaims produced")
            recommendations.append("Decomposition produced no subclaims")
            return self._score_result(0.0, 0.0, 0.0, issues, recommendations)

        if len(subclaims) == 1 and len(original.split()) > 20:
            issues.append("Single subclaim for a long claim may indicate under-splitting")
            recommendations.append("Consider splitting compound claims")

        # Check 2: Atomicity - look for compound connectors in subclaims
        compound_connectors = [" and ", " but ", " because ", " while ", " although ", " whereas ", ";" ]
        compound_count = 0
        for sc in subclaims:
            if any(conn in sc.lower() for conn in compound_connectors):
                compound_count += 1

        atomicity_score = 1.0 - min(0.5, compound_count * 0.1)
        if compound_count > 0:
            issues.append(f"{compound_count} subclaim(s) contain compound connectors that may need splitting")
            recommendations.append("Split compound subclaims at connectors like 'and', 'but', 'because'")

        # Check 3: Coverage - simple token overlap
        original_tokens = set(original.lower().split())
        subclaim_tokens = set(" ".join(subclaims).lower().split())
        coverage = len(original_tokens & subclaim_tokens) / max(1, len(original_tokens))
        coverage_score = min(1.0, coverage * 1.2)  # Slight boost since paraphrasing is ok

        # Check 4: No hallucination - check for tokens in subclaims not in original
        hallucination_tokens = subclaim_tokens - original_tokens
        # Filter out common stop words
        stop_words = {"the", "a", "an", "is", "was", "were", "are", "be", "been", "being",
                      "of", "in", "on", "at", "to", "for", "with", "by", "from", "as",
                      "that", "this", "it", "its", "or", "and", "but", "not", "no", "yes"}
        hallucination_content = hallucination_tokens - stop_words
        hallucination_ratio = len(hallucination_content) / max(1, len(subclaim_tokens))
        no_hallucination_score = max(0.0, 1.0 - hallucination_ratio * 2)
        if hallucination_content:
            issues.append(f"Subclaims contain {len(hallucination_content)} tokens not in original claim")
            recommendations.append("Ensure subclaims only paraphrase original content")

        overall = (coverage_score * 0.4 + atomicity_score * 0.3 + (1.0 - hallucination_ratio) * 0.3)

        return {
            "coverage_score": round(coverage_score, 3),
            "atomicity_score": round(atomicity_score, 3),
            "no_hallucination_score": round(no_hallucination_score, 3),
            "overall_quality": round(overall, 3),
            "issues": issues,
            "recommendations": recommendations,
            "is_acceptable": overall >= 0.7,
        }

    def _score_result(self, coverage: float, atomicity: float, no_hallucination: float,
                      issues: list[str], recommendations: list[str]) -> dict[str, Any]:
        overall = (coverage * 0.4 + atomicity * 0.3 + no_hallucination * 0.3)
        return {
            "coverage_score": round(coverage, 3),
            "atomicity_score": round(atomicity, 3),
            "no_hallucination_score": round(no_hallucination, 3),
            "overall_quality": round(overall, 3),
            "issues": issues,
            "recommendations": recommendations,
            "is_acceptable": overall >= 0.7,
        }


class SelfConsistentDecomposer:
    """Run decomposition multiple times and take consensus for higher reliability."""

    def __init__(self, llm: LLMClient | None = None, n_runs: int = 3, validator: DecompositionValidator | None = None):
        self.analyzer = ClaimAnalyzer(llm)
        self.validator = validator or DecompositionValidator()
        self.n_runs = n_runs

    def decompose_with_consensus(self, claim_text: str) -> tuple[list[str], dict[str, Any]]:
        """Run decomposition multiple times and return consensus subclaims with quality metrics."""
        if self.n_runs <= 1:
            subclaims = self.analyzer.analyze(claim_text)
            quality = self.validator.validate(claim_text, subclaims)
            return subclaims, quality

        # Run multiple decompositions
        all_runs: list[list[str]] = []
        for _ in range(self.n_runs):
            try:
                subclaims = self.analyzer.analyze(claim_text)
                if subclaims:
                    all_runs.append(subclaims)
            except Exception:
                continue

        if not all_runs:
            # Fallback to single run
            subclaims = self.analyzer.analyze(claim_text)
            quality = self.validator.validate(claim_text, subclaims)
            return subclaims, quality

        # Find consensus: subclaims that appear in majority of runs (fuzzy matching)
        from collections import Counter
        from difflib import SequenceMatcher

        # Normalize subclaims for comparison
        def normalize(sc: str) -> str:
            return " ".join(sc.lower().strip().split())

        all_subclaims = []
        for run in all_runs:
            all_subclaims.extend([normalize(sc) for sc in run])

        # Cluster similar subclaims
        clusters: list[list[str]] = []
        for sc in all_subclaims:
            matched = False
            for cluster in clusters:
                if any(SequenceMatcher(None, sc, c).ratio() > 0.8 for c in cluster):
                    cluster.append(sc)
                    matched = True
                    break
            if not matched:
                clusters.append([sc])

        # Keep clusters that appear in majority of runs
        consensus = []
        for cluster in clusters:
            if len(cluster) >= (self.n_runs + 1) // 2:  # Majority
                # Take the longest version as representative
                consensus.append(max(cluster, key=len))

        # Validate the consensus
        quality = self.validator.validate(claim_text, consensus)

        # Add consensus metadata
        quality["consensus_runs"] = len(all_runs)
        quality["consensus_subclaims"] = len(consensus)
        quality["total_subclaims_generated"] = len(all_subclaims)

        return consensus, quality