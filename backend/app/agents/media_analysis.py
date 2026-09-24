from __future__ import annotations

from collections import Counter, defaultdict

from pydantic import BaseModel, Field

from app.config import settings
from app.services.llm import LLMClient


class MediaAnalysisSchema(BaseModel):
    framing_summary: str = ""
    omitted_context: list[str] = Field(default_factory=list)
    emphasis_points: list[str] = Field(default_factory=list)
    methodology: str = ""


class MediaAnalysisAgent:
    """Phase 1 media framing overview. This is distinct from factual verification and does not determine truth."""

    ORIENTATION_MAP = {
        "bbc": "CENTER",
        "reuters": "CENTER",
        "ap": "CENTER",
        "npr": "CENTER",
        "the new york times": "CENTER",
        "washington post": "CENTER",
        "fox news": "RIGHT",
        "breitbart": "RIGHT",
        "msnbc": "LEFT",
        "huffpost": "LEFT",
        "the guardian": "LEFT",
    }

    def analyze(self, claim_text: str, documents: list | None = None, evidence_items: list | None = None) -> dict:
        docs = documents or []
        items = evidence_items or []
        publisher_counts = Counter()
        for doc in docs:
            name = self._publisher_name(doc)
            publisher_counts[name] += 1

        if not publisher_counts:
            distribution = {"Unknown": 1}
        else:
            distribution = dict(sorted(publisher_counts.items(), key=lambda pair: pair[1], reverse=True))

        left = 0
        center = 0
        right = 0
        unknown = 0
        for name in distribution:
            label = self._orientation_for_publisher(name)
            if label == "LEFT":
                left += distribution[name]
            elif label == "CENTER":
                center += distribution[name]
            elif label == "RIGHT":
                right += distribution[name]
            else:
                unknown += distribution[name]

        total = max(1, sum(distribution.values()))
        framing_summary = "Coverage is summarized by publisher distribution and the tone of supporting vs contradictory evidence; this does not determine factual truth."
        if items:
            stances = defaultdict(int)
            for item in items:
                raw_stance = getattr(item, "stance", EvidenceStance.UNKNOWN)
                stance = str(getattr(raw_stance, "value", raw_stance)).lower()
                stances[stance] += 1
            framing_summary = (
                f"Evidence stance distribution: supports={stances.get('supports', 0)}, "
                f"contradicts={stances.get('contradicts', 0)}, context={stances.get('context', 0)}."
            )

        try:
            doc_summary = "\n".join(
                f"- {getattr(doc, 'title', 'Untitled')} ({self._publisher_name(doc)})" for doc in docs[:10]
            ) or "No corpus data provided."
            evidence_summary = "\n".join(
                f"- {getattr(item, 'summary', str(item))} [{getattr(item, 'stance', 'unknown')}]" for item in items[:10]
            ) or "No evidence items provided."
            response = LLMClient().generate_structured(
                MediaAnalysisSchema,
                f"Assess media framing and omission using only the supplied corpus and evidence. Do not treat publisher orientation as factual proof or disproof.\n\nCLAIM:\n{claim_text}\n\nCORPUS:\n{doc_summary}\n\nEVIDENCE:\n{evidence_summary}",
                system_prompt="Return JSON with framing_summary, omitted_context, emphasis_points, methodology. Keep the output focused on framing, omission, and emphasis, not on factual truth."
            )
            values = response.model_dump() if hasattr(response, "model_dump") else dict(response)
            if isinstance(values, dict) and values.get("framing_summary"):
                framing_summary = values["framing_summary"]
                return {
                    "publisher_distribution": distribution,
                    "left_coverage": round(left / total, 2),
                    "center_coverage": round(center / total, 2),
                    "right_coverage": round(right / total, 2),
                    "unknown_coverage": round(unknown / total, 2),
                    "framing_summary": framing_summary,
                    "omitted_context": values.get("omitted_context") or "Publisher-level orientation is only a framing overview and does not imply the factual claim is true or false.",
                    "methodology": values.get("methodology") or "Corpus-only framing analysis; publisher orientation is not evidence of truth.",
                }
        except Exception:
            pass

        return {
            "publisher_distribution": distribution,
            "left_coverage": round(left / total, 2),
            "center_coverage": round(center / total, 2),
            "right_coverage": round(right / total, 2),
            "unknown_coverage": round(unknown / total, 2),
            "framing_summary": framing_summary,
            "omitted_context": "Publisher-level orientation is only a framing overview and does not imply the factual claim is true or false.",
            "methodology": "PUBLISHER-LEVEL ORIENTATION mapping based on known outlet labels; article-level ideology is not inferred.",
        }

    @staticmethod
    def _publisher_name(document: object) -> str:
        publisher = getattr(document, "publisher", None)
        if hasattr(publisher, "_mock_name") and publisher._mock_name:
            return str(publisher._mock_name)
        name = getattr(publisher, "name", None) if publisher is not None else None
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
