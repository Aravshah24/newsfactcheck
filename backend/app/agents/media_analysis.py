from __future__ import annotations

import logging
import math
from collections import Counter, defaultdict
from typing import Any

from pydantic import BaseModel, Field

from app.data.outlet_lean import LEAN_AS_OF, OUTLET_LEAN
from app.services.evidence_stance import normalise_stance
from app.services.llm import LLMClient, LLMUnavailableError

logger = logging.getLogger(__name__)


class MediaAnalysisSchema(BaseModel):
    framing_summary: str = ""
    omitted_context: list[str] = Field(default_factory=list)
    emphasis_points: list[str] = Field(default_factory=list)
    methodology: str = ""
    # Polarization fields
    polarization_score: float | None = None
    narrative_divergence: dict | None = None
    lean_framing: dict | None = None
    blindspots: list[str] = Field(default_factory=list)


_MEDIA_INSTRUCTION = """Summarise how coverage of a claim is distributed and framed.

This is a description of coverage, not a determination of truth. Do not say the claim is
true, false, verified, or misleading. Do not treat a publisher's political orientation as
evidence for or against the claim.

Focus on: which outlets covered it, what they emphasised, and what context the coverage
leaves out. Use only the supplied corpus and evidence summaries.

Return JSON with: framing_summary (one or two sentences), omitted_context (list),
emphasis_points (list), methodology (one short sentence).
For polarization analysis, also include:
- polarization_score (0-1): how divided coverage is across the political spectrum
- narrative_divergence: description of how LEFT/CENTER/RIGHT outlets frame the claim differently
- lean_framing: per-lean key themes/emphases
- blindspots: which lean groups have minimal or no coverage
"""


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
        "the new york times": "LEFT",
        "washington post": "LEFT",
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

        # Publisher-level distribution (backward compatible)
        publisher_counts = Counter(self._publisher_name(doc) for doc in docs)
        publisher_distribution = (
            dict(sorted(publisher_counts.items(), key=lambda pair: pair[1], reverse=True))
            if publisher_counts
            else {"Unknown": 1}
        )

        # Group documents by publisher lean
        lean_docs: dict[str, list] = defaultdict(list)
        lean_counts: Counter = Counter()
        publisher_names: dict = {}
        for doc in docs:
            name = self._publisher_name(doc)
            publisher_names[id(doc)] = name
            lean = self._orientation_for_publisher(name)
            lean_docs[lean].append(doc)
            lean_counts[lean] += 1

        # Lean-level distribution
        total = max(1, sum(lean_counts.values()))
        lean_distribution = {
            "left_coverage": round(lean_counts.get("LEFT", 0) / total, 2),
            "center_coverage": round(lean_counts.get("CENTER", 0) / total, 2),
            "right_coverage": round(lean_counts.get("RIGHT", 0) / total, 2),
            "unknown_coverage": round(lean_counts.get("UNKNOWN", 0) / total, 2),
        }

        # Stance distribution across evidence items
        stances = defaultdict(int)
        for item in items:
            stances[normalise_stance(getattr(item, "stance", "unknown"))] += 1

        # Compute polarization score (0 = single lean, 1 = evenly split across leans)
        lean_props = [lean_counts.get(l, 0) / total for l in ("LEFT", "CENTER", "RIGHT") if lean_counts.get(l, 0) > 0]
        # Use normalized entropy as polarization score
        if len(lean_props) > 1:
            entropy = -sum(p * math.log(p) for p in lean_props)
            max_entropy = math.log(len(lean_props))
            polarization_score = round(entropy / max_entropy, 3)
        else:
            polarization_score = 0.0

        # Identify blindspots (lean groups with < 10% coverage)
        blindspots = [lean for lean in ("LEFT", "CENTER", "RIGHT") if lean_counts.get(lean, 0) / total < 0.1]

        # Stance distribution summary (fallback)
        framing_summary = (
            f"Evidence stance distribution across {len(items)} assessed item(s): "
            f"supports={stances.get('supports', 0)}, contradicts={stances.get('contradicts', 0)}, "
            f"context={stances.get('context', 0)}, neutral={stances.get('neutral', 0)}."
        )
        omitted_context = (
            "Publisher-level orientation describes the distribution of coverage only and does not "
            "indicate whether the claim is true or false."
        )
        methodology = (
            "Corpus-level framing summary based on publisher distribution and assessed evidence stances. "
            "Editorial lean is per independent reviewers (AllSides, Media Bias/Fact Check, Ad Fontes Media) "
            f"as of {LEAN_AS_OF}; unrated outlets fall in the unknown bucket. Coverage is not evidence. "
            "Polarization score computed from lean distribution entropy."
        )

        # LLM-enhanced polarization analysis
        lean_framing: dict = {}
        narrative_divergence: dict | None = None

        if self.llm.is_configured():
            try:
                # Build per-lean corpus summaries for the LLM
                lean_corpus = {}
                for lean in ("LEFT", "CENTER", "RIGHT"):
                    lean_doc_names = [publisher_names[id(doc)] for doc in lean_docs.get(lean, [])]
                    if lean_doc_names:
                        lean_corpus[lean] = lean_doc_names[:10]

                response = self.llm.generate_structured(
                    MediaAnalysisSchema,
                    f"CLAIM:\n{claim_text}\n\nCORPUS BY LEAN:\n"
                    + "\n".join(f"{lean}: {', '.join(names)}" for lean, names in lean_corpus.items())
                    + f"\n\nEVIDENCE STANCES:\n{f'{dict(stances)}' if stances else 'No evidence assessed.'}",
                    system_prompt=_MEDIA_INSTRUCTION,
                )
                values = response.model_dump()

                if values.get("framing_summary"):
                    # Extract polarization fields from LLM response
                    narrative_divergence = values.get("narrative_divergence")
                    lean_framing = values.get("lean_framing", {})
                    # Ensure blindspots from LLM are included
                    llm_blindspots = values.get("blindspots", [])
                    blindspots = list(set(blindspots) | set(llm_blindspots))

                    return {
                        "publisher_distribution": publisher_distribution,
                        "lean_distribution": lean_distribution,
                        # Backward compatibility: lean distribution fields at top level
                        "left_coverage": lean_distribution["left_coverage"],
                        "center_coverage": lean_distribution["center_coverage"],
                        "right_coverage": lean_distribution["right_coverage"],
                        "unknown_coverage": lean_distribution["unknown_coverage"],
                        "polarization_score": values.get("polarization_score", polarization_score),
                        "framing_summary": values["framing_summary"],
                        "omitted_context": values.get("omitted_context") or omitted_context,
                        "emphasis_points": values.get("emphasis_points") or [],
                        "methodology": values.get("methodology") or methodology,
                        "narrative_divergence": narrative_divergence,
                        "lean_framing": lean_framing,
                        "blindspots": blindspots,
                    }
            except LLMUnavailableError as exc:
                logger.info("Media polarization analysis fell back to distribution summary: %s", exc)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Media polarization analysis failed: %s", exc)

        # Fallback without LLM
        # Build basic lean framing from document titles
        for lean in ("LEFT", "CENTER", "RIGHT"):
            if lean_docs.get(lean):
                titles = [getattr(doc, "title", "") for doc in lean_docs[lean][:5] if getattr(doc, "title", "")]
                lean_framing[lean] = titles[:5]

        # Basic narrative divergence description
        active_leans = [l for l in ("LEFT", "CENTER", "RIGHT") if lean_counts.get(l, 0) > 0]
        if len(active_leans) >= 2:
            narrative_divergence = {
                "description": f"Coverage spans {', '.join(active_leans)} outlets; framing may differ across the spectrum.",
                "active_leans": active_leans,
            }
        else:
            narrative_divergence = {
                "description": f"Coverage dominated by {active_leans[0] if active_leans else 'unknown'} outlets; limited perspective diversity.",
                "active_leans": active_leans,
            }

        return {
            "publisher_distribution": publisher_distribution,
            "lean_distribution": lean_distribution,
            # Backward compatibility
            "left_coverage": lean_distribution["left_coverage"],
            "center_coverage": lean_distribution["center_coverage"],
            "right_coverage": lean_distribution["right_coverage"],
            "unknown_coverage": lean_distribution["unknown_coverage"],
            "polarization_score": polarization_score,
            "framing_summary": framing_summary,
            "omitted_context": omitted_context,
            "emphasis_points": [],
            "methodology": methodology,
            "narrative_divergence": narrative_divergence,
            "lean_framing": lean_framing,
            "blindspots": blindspots,
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
        for token, lean in OUTLET_LEAN.items():
            if token in lowered:
                return lean.label
        for token, label in self.ORIENTATION_MAP.items():
            if token in lowered:
                return label
        return "UNKNOWN"
