"""Agent layer for fact-check investigation tasks."""

from app.agents.completeness import CompletenessAgent
from app.agents.decomposition_validator import DecompositionValidator, SelfConsistentDecomposer
from app.agents.evidence_extraction import EvidenceExtractor
from app.agents.media_analysis import MediaAnalysisAgent
from app.agents.opposition import OppositionAgent
from app.agents.source_discovery import SourceDiscoveryAgent
from app.agents.verification import VerificationAgent
from app.agents.writer import WriterAgent
from app.services.claim_analysis import ClaimAnalyzer

__all__ = [
    "ClaimAnalyzer",
    "CompletenessAgent",
    "DecompositionValidator",
    "SelfConsistentDecomposer",
    "EvidenceExtractor",
    "MediaAnalysisAgent",
    "OppositionAgent",
    "SourceDiscoveryAgent",
    "VerificationAgent",
    "WriterAgent",
]