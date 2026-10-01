from __future__ import annotations

import json
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
from app.models import (
    Claim,
    ClaimStatus,
    CompletenessResult,
    Document,
    EvidenceAssessmentStatus,
    EvidenceCategory,
    EvidenceStance,
    MediaAnalysis,
    Report,
    SearchRun,
    Subclaim,
    SubclaimConclusion,
    VerificationResult,
)
from app.retrievers.gdelt import GDELTRetriever
from app.retrievers.primary_source import PrimarySourceRetriever
from app.retrievers.web_search import WebSearchRetriever
from app.services.claim_analysis import ClaimAnalyzer
from app.services.clustering import EvidenceClusteringService
from app.services.entailment import EntailmentEngine
from app.services.evidence_stance import normalise_stance
from app.services.independence import IndependenceAnalyzer
from app.services.llm import LLMClient, llm_diagnostics

logger = logging.getLogger(__name__)

#: Verdicts that mean the investigation reached a defensible conclusion.
_CONCLUSIVE_VERDICTS = {"supported", "partially_supported", "disputed", "misleading_or_incomplete"}


class InvestigationState(TypedDict, total=False):
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
    retrieval_stats: dict
    llm_available: bool
    llm_status: dict
    session: Session
    retrievers: list[Any]
    engine: Any


class InvestigationGraph:
    """Orchestrates the investigation pipeline.

    The pipeline keeps three things separate: retrieved documents, evidence
    assessed against the complete proposition, and verified conclusions. A
    document only becomes evidence once it has been compared with the claim
    dimension by dimension, and a verdict can only rest on assessed evidence
    weighted by how many genuinely independent sources produced it.
    """

    def __init__(self, session_factory=None, engine: EntailmentEngine | None = None):
        self.session_factory = session_factory or SessionLocal
        self.engine = engine or EntailmentEngine()
        self.llm = LLMClient()
        #: Set when live reasoning is unavailable, so the pipeline never degrades silently.
        self.llm_status: dict = {}

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
        graph.add_node("dedupe_documents", self._deduplicate)
        graph.add_node("extract_evidence", self._evidence_extraction)
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
        graph.add_edge("find_primary_sources", "dedupe_documents")
        graph.add_edge("dedupe_documents", "extract_evidence")
        graph.add_edge("extract_evidence", "cluster_evidence")
        graph.add_edge("cluster_evidence", "calculate_completeness")
        graph.add_edge("calculate_completeness", "verify_claim")
        graph.add_edge("verify_claim", "summarize_verdict")
        graph.add_edge("summarize_verdict", "analyze_media")
        graph.add_edge("analyze_media", "write_report")
        graph.add_edge("write_report", END)
        return graph.compile()

    # ------------------------------------------------------------------
    # stages
    # ------------------------------------------------------------------
    def _analyze_claim(self, state: InvestigationState) -> InvestigationState:
        session: Session = state["session"]
        claim = ClaimAnalyzer(self.llm).persist_claim(session, state["claim_text"])
        state["claim_id"] = claim.id
        state["status"] = "analyzing"
        state["subclaims"] = (
            session.query(Subclaim).filter(Subclaim.claim_id == claim.id).order_by(Subclaim.priority).all()
        )
        state["errors"] = []
        state["documents"] = []
        state["evidence_items"] = []
        state["verification_results"] = []
        state["evidence"] = []
        state["report"] = ""
        state["overall_verdict"] = {}
        state["media_analysis"] = {}
        state["completeness"] = {}
        state["source_independence"] = {}
        state["primary_status"] = "NOT_CONFIGURED"
        state["retrieval_stats"] = {"search_runs": 0, "raw_documents": 0, "unique_documents": 0}
        state["llm_available"] = self.llm.is_configured()
        state["llm_status"] = self.llm_status
        state["engine"] = self.engine
        return state

    def _source_discovery(self, state: InvestigationState) -> InvestigationState:
        session: Session = state["session"]
        retrievers = state.get("retrievers") or self._default_retrievers()
        discovery_agent = SourceDiscoveryAgent(retrievers, llm=self.llm)
        documents: list[Document] = []
        for subclaim in state["subclaims"]:
            # A savepoint contains the failure to this subclaim. Rolling the whole
            # session back here would also discard documents already collected for
            # earlier subclaims, leaving stale rows that later stages cannot use.
            try:
                with session.begin_nested():
                    found = discovery_agent.discover(session, subclaim)
            except Exception as exc:  # noqa: BLE001 - isolate one subclaim's failure
                logger.exception("Source discovery failed for subclaim %s", subclaim.id)
                state["errors"].append(f"source_discovery_failed:{subclaim.id}:{exc}")
                continue
            documents.extend(found)
        self._merge_documents(state, documents)
        return state

    def _opposition_search(self, state: InvestigationState) -> InvestigationState:
        session: Session = state["session"]
        retrievers = state.get("retrievers") or self._default_retrievers()
        opposition_agent = OppositionAgent(retrievers, llm=self.llm)
        documents: list[Document] = []
        for subclaim in state["subclaims"]:
            try:
                with session.begin_nested():
                    found = [
                        document
                        for document in (
                            self._normalise(session, item, subclaim)
                            for item in opposition_agent.search_counter_evidence(subclaim, db=session)
                        )
                        if document is not None
                    ]
            except Exception as exc:  # noqa: BLE001
                logger.exception("Opposition search failed for subclaim %s", subclaim.id)
                state["errors"].append(f"opposition_failed:{subclaim.id}:{exc}")
                continue
            self._merge_documents(state, found)
        return state

    def _primary_search(self, state: InvestigationState) -> InvestigationState:
        session: Session = state["session"]
        retriever = PrimarySourceRetriever()
        if not retriever.is_available():
            state["primary_status"] = "NOT_CONFIGURED"
            return state

        documents: list[Document] = []
        found = False
        failed = False
        for subclaim in state["subclaims"]:
            try:
                results = retriever.search(subclaim, subclaim.text, max_results=settings.PRIMARY_SOURCE_MAX_RESULTS)
            except Exception as exc:  # noqa: BLE001
                failed = True
                logger.exception("Primary source search failed for subclaim %s", subclaim.id)
                state["errors"].append(f"primary_evidence_failed:{subclaim.id}:{exc}")
                continue
            if results:
                found = True
                for item in results:
                    document = self._normalise(session, item, subclaim)
                    if document is not None:
                        documents.append(document)

        state["primary_status"] = "FOUND" if found else ("SEARCH_FAILED" if failed else "NOT_FOUND")
        self._merge_documents(state, documents)
        return state

    def _deduplicate(self, state: InvestigationState) -> InvestigationState:
        from app.services.deduplication import DeduplicationService

        session: Session = state["session"]
        before = len(state["documents"])
        state["documents"] = DeduplicationService.normalize_and_dedupe(session, list(state["documents"]))
        state["retrieval_stats"]["raw_documents"] = before
        state["retrieval_stats"]["unique_documents"] = len(state["documents"])
        # Counted here so the figure reflects every channel that actually ran.
        claim_id = state.get("claim_id")
        if claim_id is not None:
            state["retrieval_stats"]["search_runs"] = (
                session.query(SearchRun).filter(SearchRun.claim_id == claim_id).count()
            )
        return state

    def _evidence_extraction(self, state: InvestigationState) -> InvestigationState:
        session: Session = state["session"]
        extractor = EvidenceExtractor(state.get("engine") or self.engine)
        documents = list(state["documents"])[: max(1, settings.EVIDENCE_MAX_DOCUMENTS_ASSESSED)]
        subclaims = state["subclaims"]
        if not documents or not subclaims:
            state["evidence_items"] = []
            state["evidence"] = []
            return state

        evidences: list = []
        engine = extractor.engine
        engine.preload_propositions([subclaim.text for subclaim in subclaims])
        propositions = [engine.proposition_for(subclaim.text) for subclaim in subclaims]

        # Documents are assessed in groups so the whole investigation costs a
        # small number of provider requests rather than one per document.
        group_size = max(1, int(settings.EVIDENCE_DOCUMENT_BATCH_SIZE))
        for start in range(0, len(documents), group_size):
            group = documents[start : start + group_size]
            payload = [
                (getattr(document, "title", "") or "", self._document_text(document)) for document in group
            ]
            try:
                assessments = engine.assess_documents(propositions, payload)
            except Exception as exc:  # noqa: BLE001 - one group must not break the pass
                logger.exception("Evidence assessment failed for documents %s-%s", start, start + len(group))
                state["errors"].append(f"evidence_assessment_failed:{start}:{exc}")
                continue

            for document_index, document in enumerate(group):
                raw_text = payload[document_index][1]
                for subclaim, proposition, assessment in zip(subclaims, propositions, assessments[document_index]):
                    try:
                        with session.begin_nested():
                            evidence = extractor.extract(
                                subclaim,
                                document,
                                raw_text,
                                proposition=proposition,
                                assessment=assessment,
                            )
                    except Exception as exc:  # noqa: BLE001
                        # The savepoint discards only this failed item; a full
                        # rollback would drop every document collected so far.
                        logger.exception("Evidence extraction failed for document %s", document.id)
                        state["errors"].append(f"evidence_extraction_failed:{document.id}:{exc}")
                        continue
                    session.add(evidence)
                    evidences.append(evidence)
        session.flush()

        state["evidence_items"] = evidences
        state["evidence"] = [
            {
                "id": evidence.id,
                "subclaim_id": evidence.subclaim_id,
                "document_id": evidence.document_id,
                "stance": normalise_stance(evidence.stance),
                "confidence": evidence.confidence_score,
                "summary": evidence.summary,
                "url": evidence.url,
                "category": str(getattr(evidence.category, "value", evidence.category)),
            }
            for evidence in evidences
        ]
        return state

    def _cluster(self, state: InvestigationState) -> InvestigationState:
        session: Session = state["session"]
        claim = session.get(Claim, state["claim_id"])
        if claim is None:
            raise RuntimeError(f"Claim {state['claim_id']} was not found for clustering.")

        analyzer = IndependenceAnalyzer()
        summary = analyzer.analyze(session, claim, state["documents"], state["evidence_items"])
        state["source_independence"] = summary.to_dict()
        # Kept as integer keys while in memory so lookups match evidence ids;
        # it is only serialised to JSON when the report row is written.
        state["source_independence"]["group_for_evidence"] = dict(summary.group_for_evidence)
        EvidenceClusteringService().cluster_from_independence(
            session, claim, summary, state["evidence_items"]
        )
        return state

    def _completeness(self, state: InvestigationState) -> InvestigationState:
        state["completeness"] = CompletenessAgent(self.llm).analyze(
            state["claim_text"], state["evidence_items"], state["subclaims"]
        )
        return state

    def _verification(self, state: InvestigationState) -> InvestigationState:
        session: Session = state["session"]
        verification_agent = VerificationAgent(self.llm)
        results: list[dict] = []

        for subclaim in state["subclaims"]:
            relevant = [
                item
                for item in state["evidence_items"]
                if str(getattr(item, "subclaim_id", None)) == str(getattr(subclaim, "id", None))
            ]
            result = verification_agent.verify(
                subclaim,
                relevant,
                completeness_result=state["completeness"],
                primary_status=state["primary_status"],
                independence_summary=state["source_independence"],
            )
            results.append(result)
            session.add(
                VerificationResult(
                    subclaim_id=subclaim.id,
                    verdict=result["verdict"],
                    confidence=result["confidence"],
                    rationale=result["rationale"],
                    supporting_evidence_count=result["supporting_evidence_count"],
                    contradicting_evidence_count=result["contradicting_evidence_count"],
                    independent_evidence_count=result["independent_supporting_groups"],
                )
            )
            self._record_verified_conclusion(session, subclaim, result, state)

        self._record_completeness(session, state)
        state["verification_results"] = results
        return state

    def _record_completeness(self, session: Session, state: InvestigationState) -> None:
        """Completeness is a claim-level analysis, so it is recorded exactly once."""
        session.add(
            CompletenessResult(
                claim_id=state["claim_id"],
                completeness_level=state["completeness"].get("completeness_status", "UNKNOWN"),
                missing_aspects={"missing_context": state["completeness"].get("missing_context", [])},
                relevant_context="; ".join(state["completeness"].get("qualifications", [])),
                confidence=state["completeness"].get("confidence", 0.5),
            )
        )
        session.flush()

    def _record_verified_conclusion(self, session: Session, subclaim, result: dict, state: InvestigationState) -> None:
        """Persist the verified conclusion separately from the raw evidence it rests on."""
        group_for_evidence = state["source_independence"].get("group_for_evidence", {}) or {}
        supporting = [
            item
            for item in state["evidence_items"]
            if str(getattr(item, "subclaim_id", None)) == str(subclaim.id)
            and normalise_stance(getattr(item, "stance", "unknown")) == EvidenceStance.SUPPORTS.value
        ]
        for item in supporting:
            item.assessment_status = EvidenceAssessmentStatus.VERIFIED
            item.category = EvidenceCategory.VERIFIED_CONCLUSION

        session.add(
            SubclaimConclusion(
                claim_id=state["claim_id"],
                subclaim_id=subclaim.id,
                verdict=result["verdict"],
                confidence=result["confidence"],
                rationale=result["rationale"],
                independent_source_groups=result.get("independent_supporting_groups", 0),
                supporting_evidence_ids=[getattr(item, "id", None) for item in supporting],
                applied_rules=result.get("applied_rules", []),
                method=result.get("method", "unknown"),
            )
        )
        session.flush()

    def _overall_verdict(self, state: InvestigationState) -> InvestigationState:
        results = state["verification_results"]
        verdicts = [result["verdict"] for result in results]
        confidence = self._aggregate(results)

        if not verdicts:
            overall = "INSUFFICIENT_EVIDENCE"
            confidence = 0.2
            explanation = "No subclaim verdicts were produced because the evidence review returned no usable results."
        elif all(verdict == "supported" for verdict in verdicts):
            overall = "SUPPORTED"
            explanation = (
                "Each subclaim has direct supporting evidence from independent sources, and no material "
                "contradictions were identified."
            )
        elif verdicts.count("disputed") >= max(1, len(verdicts) // 2):
            overall = "DISPUTED"
            explanation = "Multiple subclaims are contradicted or materially weakened by stronger opposing evidence."
        elif any(verdict == "misleading_or_incomplete" for verdict in verdicts):
            overall = "MISLEADING_OR_INCOMPLETE"
            explanation = (
                "The claim may be partly accurate but is incomplete or misleading without essential qualifiers "
                "and context."
            )
        elif any(verdict == "partially_supported" for verdict in verdicts):
            overall = "PARTIALLY_SUPPORTED"
            explanation = (
                "The claim receives partial support but requires more independent evidence or further context."
            )
        else:
            overall = "INSUFFICIENT_EVIDENCE"
            explanation = "The evidence is too limited or too inconsistent to sustain a stronger conclusion."

        state["overall_verdict"] = {
            "overall_verdict": overall,
            "overall_confidence": round(float(confidence), 2),
            "explanation": explanation,
            "primary_evidence_status": state.get("primary_status", "NOT_SEARCHED"),
        }
        return state

    @staticmethod
    def _aggregate(results: list[dict]) -> float:
        if not results:
            return 0.2
        return sum(float(result.get("confidence", 0.0)) for result in results) / len(results)

    def _media_analysis(self, state: InvestigationState) -> InvestigationState:
        session: Session = state["session"]
        data = MediaAnalysisAgent(self.llm).analyze(
            state["claim_text"], state["documents"], state["evidence_items"]
        )
        session.add(
            MediaAnalysis(
                claim_id=state["claim_id"],
                left_coverage=data.get("left_coverage"),
                center_coverage=data.get("center_coverage"),
                right_coverage=data.get("right_coverage"),
                framing_summary=data.get("framing_summary"),
                # The column is text, so structured values are serialised here and
                # decoded again by the API layer.
                omitted_context=json.dumps(data.get("omitted_context"), ensure_ascii=False)
                if isinstance(data.get("omitted_context"), (list, dict))
                else data.get("omitted_context"),
                publisher_distribution=data.get("publisher_distribution"),
                methodology=data.get("methodology"),
            )
        )
        session.flush()
        state["media_analysis"] = data
        return state

    def _writer(self, state: InvestigationState) -> InvestigationState:
        session: Session = state["session"]
        report_text = WriterAgent(self.llm).write(
            state["claim_text"],
            state["subclaims"],
            state["overall_verdict"],
            state["completeness"],
            state["evidence_items"],
            state["documents"],
            state["media_analysis"],
            state["source_independence"],
            state["verification_results"],
            primary_status=state.get("primary_status", "NOT_SEARCHED"),
        )
        independence = dict(state.get("source_independence", {}))
        # JSON columns require string keys, so the in-memory integer evidence ids
        # are stringified only at the point of persistence.
        independence["group_for_evidence"] = {
            str(key): value for key, value in (independence.get("group_for_evidence") or {}).items()
        }

        session.add(
            Report(
                claim_id=state["claim_id"],
                verdict_summary=state["overall_verdict"].get("overall_verdict"),
                overall_confidence=state["overall_verdict"].get("overall_confidence"),
                overall_explanation=state["overall_verdict"].get("explanation"),
                primary_evidence_status=state.get("primary_status", "NOT_CONFIGURED"),
                source_independence=independence,
                retrieval_stats=state.get("retrieval_stats", {}),
                llm_available=bool(state.get("llm_available", False)),
                llm_status=state.get("llm_status") or {},
                report_text=report_text,
                methodology_version="phase2-propositional",
            )
        )
        session.flush()
        state["report"] = report_text
        state["status"] = "completed"
        return state

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _document_text(document: Document) -> str:
        return (getattr(document, "text_content", None) or getattr(document, "title", None) or "").strip()

    def _normalise(self, session: Session, item: dict, subclaim) -> Document | None:
        from app.services.document_normalizer import DocumentNormalizer

        payload = dict(item)
        payload.setdefault("publisher", "Unknown publisher")
        payload.setdefault("source_type", "news")
        return DocumentNormalizer.normalize_document(
            session, payload, claim_id=subclaim.claim_id, subclaim_id=subclaim.id
        )

    @staticmethod
    def _merge_documents(state: InvestigationState, documents: list[Document]) -> None:
        seen = {document.id for document in state["documents"]}
        for document in documents:
            if document.id not in seen:
                state["documents"].append(document)
                seen.add(document.id)

    @staticmethod
    def _status_for(overall_verdict: str) -> str:
        # Verification emits SCREAMING_SNAKE verdicts, so compare case-insensitively.
        # Without this every conclusive verdict fell through to ANALYZING.
        if str(overall_verdict or "").strip().lower() in _CONCLUSIVE_VERDICTS:
            return ClaimStatus.VERIFIED.value
        return ClaimStatus.ANALYZING.value

    # ------------------------------------------------------------------
    # entry point
    # ------------------------------------------------------------------
    def run_investigation(
        self,
        claim_text: str,
        retrievers: Sequence[Any] | None = None,
        session_factory=None,
        session: Session | None = None,
    ) -> dict[str, Any]:
        """Run the investigation to completion.

        When a ``session`` is supplied the caller keeps ownership of it and the
        graph will not close it. Otherwise a session is created from the factory
        and closed here.
        """
        owns_session = session is None
        active_session = session if session is not None else (session_factory or self.session_factory)()

        # A single live probe up front records whether real reasoning is possible,
        # so a degraded run is reported as degraded rather than looking normal.
        self.llm_status = llm_diagnostics(probe=True)
        llm_available = bool(self.llm_status.get("available"))
        if not llm_available:
            logger.warning(
                "Live LLM reasoning is unavailable (%s): %s",
                self.llm_status.get("error_code"),
                self.llm_status.get("remediation"),
            )

        try:
            state: InvestigationState = {
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
                "primary_status": "NOT_CONFIGURED",
                "retrieval_stats": {},
                "llm_available": llm_available,
                "llm_status": self.llm_status,
                "retrievers": list(retrievers if retrievers is not None else self._default_retrievers()),
                "session": active_session,
                "engine": self.engine,
            }
            output = self.build_graph().invoke(state)

            claim = active_session.get(Claim, output["claim_id"])
            if claim is None:
                active_session.rollback()
                return {"claim_id": None, "status": "failed", "errors": ["Claim was not persisted."]}

            claim.status = self._status_for(output["overall_verdict"].get("overall_verdict", ""))
            active_session.commit()

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
                "retrieval_stats": output.get("retrieval_stats", {}),
                "source_independence": output["source_independence"],
                "completeness": output["completeness"],
                "verification_results": output["verification_results"],
                "media_analysis": output["media_analysis"],
                "overall_verdict": output["overall_verdict"],
                "primary_evidence_status": output.get("primary_status", "NOT_CONFIGURED"),
                "llm_available": output.get("llm_available", False),
                "llm_status": output.get("llm_status", self.llm_status),
                "report": output["report"],
                "evidence": output["evidence"],
            }
        except Exception as exc:  # noqa: BLE001 - surface failure to the caller
            active_session.rollback()
            logger.exception("Investigation workflow failed for claim_text=%s", claim_text)
            return {
                "claim_id": None,
                "status": "failed",
                "errors": [str(exc)],
                "subclaims": [],
                "documents": [],
                "evidence_count": 0,
            }
        finally:
            if owns_session:
                active_session.close()
