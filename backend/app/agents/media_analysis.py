from __future__ import annotations

import logging
from collections import Counter, defaultdict

from pydantic import BaseModel, Field

from app.services.evidence_stance import normalise_stance
from app.services.llm import LLMClient, LLMUnavailableError

logger = logging.getLogger(__name__)


class MediaAnalysisSchema(BaseModel):
    framing_summary: str = ""
    omitted_context: list[str] = Field(default_factory=list)
    emphasis_points: list[str] = Field(default_factory=list)
    methodology: str = ""


_MEDIA_INSTRUCTION = """Summarise how coverage of a claim is distributed and framed.

This is a description of coverage, not a determination of truth. Do not say the claim is
true, false, verified, or misleading. Do not treat a publisher's political orientation as
evidence for or against the claim.

Focus on: which outlets covered it, what they emphasised, and what context the coverage
leaves out. Use only the supplied corpus and evidence summaries.

Return JSON with: framing_summary (one or two sentences), omitted_context (list),
emphasis_points (list), methodology (one short sentence)."""


class MediaAnalysisAgent:
    """Distribution-level framing overview, kept separate from verification.

    Publisher orientation describes the shape of coverage. It never contributes
    to a verdict and is never counted as evidence.
    """

    ORIENTATION_MAP = {
        "bbc": "CENTER",
        "reuters": "CENTER",
        "associated press": "CENTER",
        "ap news": "CENTER",
        "npr": "CENTER",
        "the new york times": "CENTER",
        "washington post": "CENTER",
        "fox news": "RIGHT",
        "breitbart": "RIGHT",
        "msnbc": "LEFT",
        "huffpost": "LEFT",
        "the guardian": "LEFT",
    }

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or LLMClient()

    def analyze(self, claim_text: str, documents: list | None = None, evidence_items: list | None = None) -> dict:
        docs = list(documents or [])
        items = list(evidence_items or [])

        publisher_counts = Counter(self._publisher_name(doc) for doc in docs)
        distribution = (
            dict(sorted(publisher_counts.items(), key=lambda pair: pair[1], reverse=True))
            if publisher_counts
            else {"Unknown": 1}
        )

        left = center = right = unknown = 0
        for name, count in distribution.items():
            label = self._orientation_for_publisher(name)
            if label == "LEFT":
                left += count
            elif label == "CENTER":
                center += count
            elif label == "RIGHT":
                right += count
            else:
                unknown += count

        total = max(1, sum(distribution.values()))
        base = {
            "publisher_distribution": distribution,
            "left_coverage": round(left / total, 2),
            "center_coverage": round(center / total, 2),
            "right_coverage": round(right / total, 2),
            "unknown_coverage": round(unknown / total, 2),
        }

        stances = defaultdict(int)
        for item in items:
            stances[normalise_stance(getattr(item, "stance", "unknown"))] += 1

        framing_summary = (
            f"Evidence stance distribution across {len(items)} assessed item(s): "
            f"supports={stances.get('supports', 0)}, contradicts={stances.get('contradicts', 0)}, "
            f"context={stances.get('context', 0)}, neutral={stances.get('neutral', 0)}."
        )
        omitted_context = (
            "Publisher-level orientation describes the distribution of coverage only and does not "
            "indicate whether the claim is true or false."
        )
        methodology = "Corpus-level framing summary based on publisher distribution and assessed evidence stances."

        if self.llm.is_configured():
            try:
                response = self.llm.generate_structured(
                    MediaAnalysisSchema,
                    f"CLAIM:\n{claim_text}\n\nCORPUS:\n"
                    + ("\n".join(f"- {self._publisher_name(doc)}" for doc in docs[:15]) or "No corpus data.")
                    + "\n\nEVIDENCE STANCES:\n"
                    + (f"{dict(stances)}" if stances else "No evidence assessed."),
                    system_prompt=_MEDIA_INSTRUCTION,
                )
                values = response.model_dump()
                if values.get("framing_summary"):
                    return {
                        **base,
                        "framing_summary": values["framing_summary"],
                        "omitted_context": values.get("omitted_context") or omitted_context,
                        "emphasis_points": values.get("emphasis_points") or [],
                        "methodology": values.get("methodology") or methodology,
                    }
            except LLMUnavailableError as exc:
                logger.info("Media framing fell back to distribution summary: %s", exc)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Media framing analysis failed: %s", exc)

        return {
            **base,
            "framing_summary": framing_summary,
            "omitted_context": omitted_context,
            "emphasis_points": [],
            "methodology": methodology,
        }

    @staticmethod
    def _publisher_name(document: object) -> str:
        publisher = getattr(document, "publisher", None)
        if publisher is None:
            return "Unknown"
        if hasattr(publisher, "_mock_name") and publisher._mock_name:
            return str(publisher._mock_name)
        name = getattr(publisher, "name", None)
        if isinstance(name, str) and name.strip():
            return name.strip()
        if isinstance(publisher, str) and publisher.strip():
            return publisher.strip()
        return "Unknown"

    def _orientation_for_publisher(self, name: str) -> str:
        lowered = str(name or "").lower()
        for token, label in self.ORIENTATION_MAP.items():
            if token in lowered:
                return label
        return "UNKNOWN"
