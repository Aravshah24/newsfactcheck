from __future__ import annotations

import logging
from typing import Any, Sequence, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents.completeness import CompletenessAgent
from app.agents.evidence_extraction import EvidenceExtractor
from app.agents.media_analysis import MediaAnalysisAgent
from app.agents.opposition import OppositionAgent
from app.agents.source_discovery import SourceDiscoveryAgent
from app.agents.verification import VerificationAgent
from app.agents.writer import WriterAgent
from app.config import settings
from app.db.session import SessionLocal
from app.models import ClaimStatus, CompletenessResult, MediaAnalysis, Report, VerificationResult
from app.retrievers.gdelt import GDELTRetriever
from app.retrievers.primary_source import PrimarySourceRetriever
from app.retrievers.web_search import WebSearchRetriever
from app.services.claim_analysis import ClaimAnalyzer
from app.services.clustering import EvidenceClusteringService
from app.services.deduplication import DeduplicationService
from app.services.document_normalizer import DocumentNormalizer

logger = logging.getLogger(__name__)


class InvestigationState(TypedDict):
    claim_text: str
    claim_id: int | None
    status: str
    subclaims: list
    documents: list
    evidence_items: list
    errors: list[str]
    completeness: dict
    verification_results: list
    source_independence: dict
    media_analysis: dict
    overall_verdict: dict
    report: str
    evidence: list
    primary_status: str
    session: Session
    retrievers: list[Any]


class InvestigationGraph:
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or SessionLocal

    @staticmethod
    def _default_retrievers() -> list[Any]:
        retrievers: list[Any] = [GDELTRetriever(), WebSearchRetriever()]
        if settings.PRIMARY_SOURCE_PROVIDER and settings.PRIMARY_SOURCE_API_KEY:
            retrievers.append(PrimarySourceRetriever())
        return retrievers

    def build_graph(self):
        graph = StateGraph(InvestigationState)

        graph.add_node("analyze_claim", self._analyze_claim)
        graph.add_node("discover_sources", self._source_discovery)
        graph.add_node("check_opposition", self._opposition_search)
        graph.add_node("find_primary_sources", self._primary_search)
        graph.add_node("extract_evidence", self._evidence_extraction)
        graph.add_node("dedupe_documents", self._deduplicate)
        graph.add_node("cluster_evidence", self._cluster)
        graph.add_node("calculate_completeness", self._completeness)
        graph.add_node("verify_claim", self._verification)
        graph.add_node("summarize_verdict", self._overall_verdict)
        graph.add_node("analyze_media", self._media_analysis)
        graph.add_node("write_report", self._writer)

        graph.set_entry_point("analyze_claim")
        graph.add_edge("analyze_claim", "discover_sources")
        graph.add_edge("discover_sources", "check_opposition")
        graph.add_edge("check_opposition", "find_primary_sources")
        graph.add_edge("find_primary_sources", "extract_evidence")
        graph.add_edge("extract_evidence", "dedupe_documents")
        graph.add_edge("dedupe_documents", "cluster_evidence")
        graph.add_edge("cluster_evidence", "calculate_completeness")
        graph.add_edge("calculate_completeness", "verify_claim")
        graph.add_edge("verify_claim", "summarize_verdict")
        graph.add_edge("summarize_verdict", "analyze_media")
        graph.add_edge("analyze_media", "write_report")
        graph.add_edge("write_report", END)
        return graph.compile()

    def _analyze_claim(self, state: InvestigationState):
        session: Session = state.get("session")
        claim_text = state["claim_text"]
        claim = ClaimAnalyzer().persist_claim(session, claim_text)
        state["claim_id"] = claim.id
        state["status"] = "analyzing"
        state["subclaims"] = session.query(type(claim.subclaims[0]) if claim.subclaims else object).filter_by(claim_id=claim.id).order_by(type(claim.subclaims[0]).priority).all() if claim.subclaims else []
        if not state["subclaims"]:
            from app.models import Subclaim
            state["subclaims"] = session.query(Subclaim).filter(Subclaim.claim_id == claim.id).order_by(Subclaim.priority).all()
        state["errors"] = []
        state["documents"] = []
        state["evidence_items"] = []
        state["verification_results"] = []
        state["report"] = ""
        state["overall_verdict"] = {}
        state["media_analysis"] = {}
        state["completeness"] = {}
        state["source_independence"] = {}
        state["primary_status"] = "NOT_FOUND"
        return state

    def _source_discovery(self, state: InvestigationState):
        session: Session = state.get("session")
        subclaims = state["subclaims"]
        retrievers = state.get("retrievers", self._default_retrievers())
        discovery_agent = SourceDiscoveryAgent(retrievers)
        documents = []
        for subclaim in subclaims:
            try:
                docs = discovery_agent.discover(session, subclaim)
                documents.extend(docs)
            except Exception as exc:
                session.rollback()
                logger.exception("Source discovery failed for subclaim %s", subclaim.id)
                state["errors"].append(f"source_discovery_failed:{subclaim.id}:{exc}")
        state["documents"] = documents
        return state

    def _opposition_search(self, state: InvestigationState):
        session: Session = state.get("session")
        subclaims = state["subclaims"]
        retrievers = state.get("retrievers", self._default_retrievers())
        for subclaim in subclaims:
            try:
                counter_documents = OppositionAgent(retrievers).search_counter_evidence(subclaim)
                for item in counter_documents:
                    doc = DocumentNormalizer.normalize_document(session, item, claim_id=subclaim.claim_id, subclaim_id=subclaim.id)
                    state["documents"].append(doc)
            except Exception as exc:
                session.rollback()
                logger.exception("Opposition search failed for subclaim %s", subclaim.id)
                state["errors"].append(f"opposition_failed:{subclaim.id}:{exc}")
        return state

    def _primary_search(self, state: InvestigationState):
        session: Session = state.get("session")
        subclaims = state["subclaims"]
        primary_retriever = PrimarySourceRetriever()
        if not primary_retriever.is_available():
            return state
        for subclaim in subclaims:
            try:
                result = primary_retriever.search(subclaim, subclaim.text, max_results=5)
                for item in result:
                    doc = DocumentNormalizer.normalize_document(session, item, claim_id=subclaim.claim_id, subclaim_id=subclaim.id)
                    state["documents"].append(doc)
                if result:
                    state["primary_status"] = "FOUND"
            except Exception as exc:
                session.rollback()
                logger.exception("Primary source search failed for subclaim %s", subclaim.id)
                state["errors"].append(f"primary_evidence_failed:{subclaim.id}:{exc}")
        return state

    def _evidence_extraction(self, state: InvestigationState):
        session: Session = state.get("session")
        evidences = []
        for document in state["documents"]:
            for subclaim in state["subclaims"]:
                raw_text = document.text_content or document.title or subclaim.text
                evidence = EvidenceExtractor().extract(subclaim, document, raw_text)
                session.add(evidence)
                evidences.append(evidence)
        state["evidence_items"] = evidences
        state["evidence"] = [
            {
                "id": evidence.id,
                "subclaim_id": evidence.subclaim_id,
                "document_id": evidence.document_id,
                "summary": evidence.summary,
                "stance": str(evidence.stance),
                "url": evidence.url,
            }
            for evidence in evidences
        ]
        session.flush()
        return state

    def _deduplicate(self, state: InvestigationState):
        session: Session = state.get("session")
        deduped = DeduplicationService.normalize_and_dedupe(session, list(state["documents"]))
        state["documents"] = deduped
        return state

    def _cluster(self, state: InvestigationState):
        session: Session = state.get("session")
        claim = session.get(__import__('app.models', fromlist=['Claim']).Claim, state["claim_id"])
        if claim is None:
            from app.models import Claim
            claim = session.query(Claim).filter_by(id=state["claim_id"]).first()
        if claim is None:
            raise RuntimeError(f"Claim {state['claim_id']} was not found for clustering.")
        cluster_service = EvidenceClusteringService()
        created = cluster_service.cluster_by_document_hash(session, claim)
        state["source_independence"] = {
            "documents_found": len(state["documents"]),
            "distinct_publishers": len({doc.publisher.name for doc in state["documents"] if getattr(doc, "publisher", None) is not None}),
            "evidence_clusters": len(created),
            "estimated_independent_sources": max(1, len(created) or len({doc.publisher.name for doc in state["documents"] if getattr(doc, "publisher", None) is not None})),
            "duplicate_derived_documents": max(0, len(state["documents"]) - len(set(doc.id for doc in state["documents"]))),
        }
        return state

    def _completeness(self, state: InvestigationState):
        state["completeness"] = CompletenessAgent().analyze(state["claim_text"], state["evidence_items"], state["subclaims"])
        return state

    def _verification(self, state: InvestigationState):
        session: Session = state.get("session")
        subclaims = state["subclaims"]
        verification_results = []
        for subclaim in subclaims:
            relevant_evidence = [item for item in state["evidence_items"] if getattr(item, "subclaim_id", None) == subclaim.id]
            result = VerificationAgent().verify(
                subclaim,
                relevant_evidence,
                completeness_result=state["completeness"],
                primary_status=state["primary_status"],
                independence_summary=state["source_independence"],
            )
            verification_results.append(result)
            session.add(VerificationResult(
                subclaim_id=subclaim.id,
                verdict=result["verdict"],
                confidence=result["confidence"],
                rationale=result["rationale"],
                supporting_evidence_count=result["supporting_evidence_count"],
                contradicting_evidence_count=result["contradicting_evidence_count"],
                independent_evidence_count=state["source_independence"].get("estimated_independent_sources", 1),
            ))
            session.add(CompletenessResult(
                claim_id=state["claim_id"],
                completeness_level=state["completeness"].get("completeness_status", "UNKNOWN"),
                missing_aspects={"missing_context": state["completeness"].get("missing_context", [])},
                relevant_context="; ".join(state["completeness"].get("qualifications", [])),
                confidence=state["completeness"].get("confidence", 0.5),
            ))
        state["verification_results"] = verification_results
        return state

    def _overall_verdict(self, state: InvestigationState):
        results = state["verification_results"]
        verdicts = [result["verdict"] for result in results]
        if not verdicts:
            overall = "INSUFFICIENT_EVIDENCE"
            confidence = 0.2
            explanation = "No subclaim verdicts were produced because the evidence review did not return usable results."
        elif all(v == "supported" for v in verdicts):
            overall = "SUPPORTED"
            confidence = sum(r["confidence"] for r in results) / max(1, len(results))
            explanation = "Each subclaim has direct supporting evidence, and no material contradictions were identified."
        elif verdicts.count("disputed") >= max(1, len(verdicts) // 2):
            overall = "DISPUTED"
            confidence = sum(r["confidence"] for r in results) / max(1, len(results))
            explanation = "Multiple subclaims are contradicted or materially weakened by stronger opposing evidence."
        elif any(v == "misleading_or_incomplete" for v in verdicts):
            overall = "MISLEADING_OR_INCOMPLETE"
            confidence = sum(r["confidence"] for r in results) / max(1, len(results))
            explanation = "The claim may be partially true but is incomplete or misleading without essential qualifiers and context."
        elif any(v == "partially_supported" for v in verdicts):
            overall = "PARTIALLY_SUPPORTED"
            confidence = sum(r["confidence"] for r in results) / max(1, len(results))
            explanation = "The claim receives partial support but requires important context and more independent evidence."
        else:
            overall = "INSUFFICIENT_EVIDENCE"
            confidence = sum(r["confidence"] for r in results) / max(1, len(results))
            explanation = "The evidence is too limited or too inconsistent to sustain a stronger conclusion."

        state["overall_verdict"] = {
            "overall_verdict": overall,
            "overall_confidence": round(float(confidence), 2),
            "explanation": explanation,
        }
        return state

    def _media_analysis(self, state: InvestigationState):
        session: Session = state.get("session")
        claim = session.get(__import__('app.models', fromlist=['Claim']).Claim, state["claim_id"])
        data = MediaAnalysisAgent().analyze(state["claim_text"], state["documents"], state["evidence_items"])
        session.add(MediaAnalysis(
            claim_id=state["claim_id"],
            left_coverage=data.get("left_coverage"),
            center_coverage=data.get("center_coverage"),
            right_coverage=data.get("right_coverage"),
            framing_summary=data.get("framing_summary"),
            omitted_context=data.get("omitted_context"),
            publisher_distribution=data.get("publisher_distribution"),
            methodology=data.get("methodology"),
        ))
        state["media_analysis"] = data
        return state

    def _writer(self, state: InvestigationState):
        session: Session = state.get("session")
        report_text = WriterAgent().write(
            state["claim_text"],
            state["subclaims"],
            state["overall_verdict"],
            state["completeness"],
            state["evidence_items"],
            state["documents"],
            state["media_analysis"],
            state["source_independence"],
            state["verification_results"],
        )
        session.add(Report(
            claim_id=state["claim_id"],
            verdict_summary=state["overall_verdict"].get("overall_verdict"),
            report_text=report_text,
            methodology_version="phase1-demo",
        ))
        state["report"] = report_text
        state["status"] = "completed"
        return state

    def run_investigation(
        self,
        claim_text: str,
        retrievers: Sequence[Any] | None = None,
        session_factory=None,
    ) -> dict[str, Any]:
        factory = session_factory or self.session_factory
        session = factory()
        try:
            state = {
                "claim_text": claim_text,
                "claim_id": None,
                "status": "starting",
                "subclaims": [],
                "documents": [],
                "evidence_items": [],
                "errors": [],
                "completeness": {},
                "verification_results": [],
                "source_independence": {},
                "media_analysis": {},
                "overall_verdict": {},
                "report": "",
                "evidence": [],
                "primary_status": "NOT_FOUND",
                "retrievers": list(retrievers or self._default_retrievers()),
                "session": session,
            }
            output = self.build_graph().invoke(state)
            claim = session.get(__import__('app.models', fromlist=['Claim']).Claim, output["claim_id"])
            if claim is not None:
                claim.status = ClaimStatus.VERIFIED.value
                session.commit()
            else:
                session.rollback()
                return {
                    "claim_id": None,
                    "status": "failed",
                    "errors": ["Claim was not persisted."]
                }

            return {
                "claim_id": output["claim_id"],
                "claim_text": claim_text,
                "status": output["status"],
                "subclaims": [
                    {"id": subclaim.id, "text": subclaim.text, "type": subclaim.subclaim_type}
                    for subclaim in output["subclaims"]
                ],
                "documents": [document.id for document in output["documents"]],
                "evidence_count": len(output["evidence_items"]),
                "errors": output["errors"],
                "source_independence": output["source_independence"],
                "completeness": output["completeness"],
                "verification_results": output["verification_results"],
                "media_analysis": output["media_analysis"],
                "overall_verdict": output["overall_verdict"],
                "report": output["report"],
                "evidence": output["evidence"],
            }
        except Exception as exc:
            session.rollback()
            logger.exception("Investigation workflow failed for claim_text=%s", claim_text)
            return {
                "claim_id": None,
                "status": "failed",
                "errors": [str(exc)],
                "subclaims": [],
                "documents": [],
                "evidence_count": 0,
                "clusters": 0,
            }
        finally:
            session.close()
