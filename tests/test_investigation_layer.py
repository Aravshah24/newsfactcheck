from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.agents.completeness import CompletenessAgent
from app.agents.media_analysis import MediaAnalysisAgent
from app.agents.opposition import OppositionAgent
from app.agents.source_discovery import SourceDiscoveryAgent
from app.agents.writer import WriterAgent
from app.db.base import Base
from app.db.session import get_db
from app.graph.investigation import InvestigationGraph
from app.models import (
    Claim,
    ClaimStatus,
    Document,
    DocumentSourceType,
    EvidenceItem,
    EvidenceStance,
    Publisher,
    PublisherType,
    Report,
    SearchChannel,
    Subclaim,
    SubclaimType,
)
from app.retrievers.gdelt import GDELTRetriever
from app.retrievers.primary_source import PrimarySourceRetriever
from app.retrievers.web_search import WebSearchRetriever
from app.services.claim_analysis import ClaimAnalyzer
from app.services.entailment import EntailmentEngine, EntailmentResult
from app.services.llm import LLMUnavailableError
from app.services.proposition import Proposition, PropositionSchema


@pytest.fixture
def session() -> Session:
    # StaticPool keeps one connection alive so the in-memory database is visible
    # across threads, which the TestClient and the graph's background work use.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with Session(bind=engine) as db:
        yield db


class ScriptedEngine(EntailmentEngine):
    """Offline engine: returns a fixed comparison so pipeline tests need no LLM."""

    def __init__(self, response: dict):
        self.response = response
        self._proposition_cache: dict[str, Proposition] = {}

    def proposition_for(self, claim_text: str) -> Proposition:
        return Proposition(claim_text, {"subject": "s", "action": "a"}, degraded=False)

    def preload_propositions(self, claim_texts: list[str]) -> dict[str, Proposition]:
        return {}

    def assess(self, proposition, evidence_text, document_title="") -> EntailmentResult:
        from app.services.entailment import DimensionComparison

        comparisons = [DimensionComparison(**item) for item in self.response.get("dimensions", [])]
        return EntailmentResult(
            stance=self.response["stance"],
            confidence=self.response.get("confidence", 0.5),
            rationale=self.response.get("rationale", "scripted"),
            dimension_status={item.dimension: item.status for item in comparisons},
            dimension_conflicts={item.dimension: item.evidence_value for item in comparisons if item.status == "conflict"},
            method="scripted",
        )

    def assess_many(self, propositions, evidence_text, document_title="") -> list[EntailmentResult]:
        return [self.assess(proposition, evidence_text, document_title) for proposition in propositions]


def _scripted(stance: str, dimensions: list[dict], confidence: float = 0.5) -> ScriptedEngine:
    return ScriptedEngine({"stance": stance, "dimensions": dimensions, "confidence": confidence})


def _offline_llm():
    """Force every agent onto its deterministic fallback so tests need no API key."""
    from contextlib import ExitStack

    stack = ExitStack()
    for target in (
        "app.services.claim_analysis.LLMClient.generate_structured",
        "app.services.proposition.LLMClient.generate_structured",
        "app.services.entailment.LLMClient.generate_structured",
        "app.agents.source_discovery.LLMClient.generate_structured",
        "app.agents.opposition.LLMClient.generate_structured",
        "app.agents.completeness.LLMClient.generate_structured",
        "app.agents.verification.LLMClient.generate_structured",
        "app.agents.media_analysis.LLMClient.generate_structured",
    ):
        stack.enter_context(patch(target, side_effect=LLMUnavailableError("offline in tests")))
    stack.enter_context(patch("app.agents.writer.LLMClient.is_configured", return_value=False))
    return stack


# ----------------------------------------------------------------------
# Claim analysis
# ----------------------------------------------------------------------
def test_claim_analyzer_keeps_a_single_statement_intact() -> None:
    with patch("app.services.claim_analysis.LLMClient.generate_structured", side_effect=LLMUnavailableError("x")):
        analyzer = ClaimAnalyzer()
        claim, subclaims = analyzer.build_claim_record("The city council approved the budget.")
    assert claim.claim_text == "The city council approved the budget."
    assert len(subclaims) == 1
    assert subclaims[0].subclaim_type == SubclaimType.FACTUAL.value


def test_claim_analyzer_splits_a_compound_claim_into_checkable_parts() -> None:
    with patch("app.services.claim_analysis.LLMClient.generate_structured", side_effect=LLMUnavailableError("x")):
        analyzer = ClaimAnalyzer()
        claim, subclaims = analyzer.build_claim_record(
            "The company hired 50 employees and the hiring caused revenue to rise 20% after 2024."
        )
    assert len(subclaims) >= 2
    assert all(sub.text.strip() for sub in subclaims)


def test_claim_analyzer_uses_the_model_when_available() -> None:
    with patch("app.services.claim_analysis.LLMClient.generate_structured") as generate:
        generate.return_value = Mock(subclaims=["First proposition.", "Second proposition."])
        subclaims = ClaimAnalyzer().analyze("A claim with two parts.")
    generate.assert_called_once()
    assert subclaims == ["First proposition.", "Second proposition."]


def test_claim_analyzer_requires_a_non_empty_claim() -> None:
    with pytest.raises(ValueError):
        ClaimAnalyzer().analyze("   ")


# ----------------------------------------------------------------------
# Retrievers
# ----------------------------------------------------------------------
def test_gdelt_result_normalization() -> None:
    item = {
        "title": "Example article",
        "url": "https://example.com/story",
        "publisher": "Example Press",
        "domain": "example.com",
        "language": "English",
        "seendate": "20240901010101",
        "publisheddate": "20240901",
        "sourcecountry": "US",
    }
    normalized = GDELTRetriever.normalize_result(item)
    assert normalized["title"] == "Example article"
    assert normalized["url"] == "https://example.com/story"
    assert normalized["publisher"] == "Example Press"
    assert normalized["retrieval_channel"] == SearchChannel.GDELT.value


def test_gdelt_zero_results() -> None:
    with patch("app.retrievers.gdelt.httpx.get") as mock_get:
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.return_value = {"articles": []}
        results = GDELTRetriever().search(subclaim=None, query="No results query", max_results=5)
    assert results == []


def test_gdelt_api_failure_is_contained() -> None:
    with patch("app.retrievers.gdelt.httpx.get", side_effect=RuntimeError("failure")):
        results = GDELTRetriever().search(subclaim=None, query="Failure query", max_results=5)
    assert results == []


def test_web_search_is_unavailable_without_configuration() -> None:
    with patch("app.retrievers.web_search.settings.WEB_SEARCH_PROVIDER", None), patch(
        "app.retrievers.web_search.settings.WEB_SEARCH_API_KEY", None
    ), patch("app.retrievers.web_search.settings.WEB_SEARCH_ENDPOINT", None):
        retriever = WebSearchRetriever()
        assert retriever.is_available() is False
        assert retriever.search(subclaim=None, query="anything") == []


def test_primary_source_reports_not_configured_rather_than_failing() -> None:
    with patch("app.retrievers.primary_source.settings.PRIMARY_SOURCE_PROVIDER", None):
        retriever = PrimarySourceRetriever()
        assert retriever.is_available() is False
        assert retriever.search(subclaim=None, query="agency report") == []
    assert retriever.last_status == "NOT_CONFIGURED"


def test_primary_source_classifies_official_and_institutional_sources() -> None:
    retriever = PrimarySourceRetriever()
    assert retriever.classify("https://data.gov.example/report", "Report", "Agency") == DocumentSourceType.PRIMARY
    assert (
        retriever.classify("https://example.com/x", "Ministry of Statistics bulletin", "Ministry of Statistics")
        == DocumentSourceType.AUTHORITATIVE
    )
    assert retriever.classify("https://blog.example/x", "A blog post", "Some Blog") == DocumentSourceType.OTHER


# ----------------------------------------------------------------------
# Opposition and discovery
# ----------------------------------------------------------------------
def test_opposition_agent_generates_counter_queries() -> None:
    with patch("app.agents.opposition.LLMClient.generate_structured", side_effect=LLMUnavailableError("x")):
        queries = OppositionAgent(retrievers=[]).generate_queries("The company raised prices and sales fell in 2024.")
    assert len(queries) >= 2
    assert any(word in q.lower() for q in queries for word in ("correction", "denied", "disputed", "inaccurate", "record"))


def test_opposition_agent_collects_counter_documents_across_channels() -> None:
    first = Mock(channel_name="gdelt")
    first.search.return_value = [
        {"title": "Disputing report", "url": "https://example.com/rebuttal", "content": "A rebuttal."}
    ]
    second = Mock(channel_name="web_search")
    second.search.return_value = [
        {"title": "Official record", "url": "https://example.gov/record", "content": "The official record."}
    ]

    claim = Claim(claim_text="A claim.")
    subclaim = Subclaim(claim=claim, text="A claim.", subclaim_type=SubclaimType.FACTUAL.value)
    results = OppositionAgent(retrievers=[first, second]).search_counter_evidence(subclaim)

    assert len(results) >= 2
    assert all(item.get("search_intent") == "opposition" for item in results)
    assert {item["url"] for item in results} == {"https://example.com/rebuttal", "https://example.gov/record"}


def test_opposition_agent_survives_a_failing_channel() -> None:
    broken = Mock(channel_name="broken")
    broken.search.side_effect = RuntimeError("channel down")
    working = Mock(channel_name="gdelt")
    working.search.return_value = [{"title": "A", "url": "https://example.com/a", "content": "text"}]

    claim = Claim(claim_text="A claim.")
    subclaim = Subclaim(claim=claim, text="A claim.", subclaim_type=SubclaimType.FACTUAL.value)
    results = OppositionAgent(retrievers=[broken, working]).search_counter_evidence(subclaim)
    assert [item["url"] for item in results] == ["https://example.com/a"]


def test_source_discovery_deduplicates_at_ingestion(session: Session) -> None:
    claim = Claim(claim_text="A claim.")
    subclaim = Subclaim(claim=claim, text="A claim.", subclaim_type=SubclaimType.FACTUAL.value)
    session.add_all([claim, subclaim])
    session.flush()

    results = [
        {"title": "Story", "url": "https://wire.example/story", "publisher": "Wire", "content": "The shared body text."},
        {
            "title": "Story",
            "url": "https://mirror.example/story",
            "publisher": "Mirror",
            "content": "The shared body text.",
        },
    ]
    retriever = Mock(channel_name="gdelt")
    retriever.search.return_value = results

    with patch("app.agents.source_discovery.LLMClient.generate_structured", side_effect=LLMUnavailableError("x")):
        documents = SourceDiscoveryAgent([retriever]).discover(session, subclaim)

    # A republished copy is collapsed at ingestion so it can never become a second item.
    assert len(documents) == 1


def test_discovery_keeps_documents_from_subclaims_that_succeeded(session: Session) -> None:
    """A later subclaim failing must not discard documents found for earlier ones.

    Rolling the whole session back on failure used to leave the earlier documents
    pending in memory but missing from the database, so the later relationship
    insert failed on a stale document id and aborted the investigation.
    """
    claim = Claim(claim_text="A claim.")
    first = Subclaim(claim=claim, text="First part.", subclaim_type=SubclaimType.FACTUAL.value)
    second = Subclaim(claim=claim, text="Second part.", subclaim_type=SubclaimType.FACTUAL.value)
    session.add_all([claim, first, second])
    session.flush()

    graph = InvestigationGraph()

    class _FlakyDiscovery:
        calls = 0

        def discover(self, db, subclaim):
            _FlakyDiscovery.calls += 1
            if subclaim.id == second.id:
                raise RuntimeError("retriever exploded")
            return SourceDiscoveryAgent(
                [
                    Mock(
                        channel_name="gdelt",
                        search=Mock(
                            return_value=[
                                {
                                    "title": "Story",
                                    "url": "https://wire.example/story",
                                    "publisher": "Wire",
                                    "content": "Body text.",
                                }
                            ]
                        ),
                    )
                ]
            ).discover(db, subclaim)

    state: dict = {
        "session": session,
        "subclaims": [first, second],
        "documents": [],
        "errors": [],
        "retrieval_stats": {},
    }
    graph.llm = Mock(llm_status={}, is_configured=Mock(return_value=False))
    with patch("app.graph.investigation.SourceDiscoveryAgent", return_value=_FlakyDiscovery()):
        result = graph._source_discovery(state)

    assert any("source_discovery_failed" in error for error in result["errors"])
    assert len(result["documents"]) == 1
    document = result["documents"][0]
    # The surviving document must still be a real, persisted row.
    assert session.get(Document, document.id) is document


def test_duplicate_relationship_edge_does_not_abort_the_investigation(session: Session) -> None:
    """A duplicate edge is skipped rather than failing the whole run."""
    from app.models import SourceRelationshipType
    from app.services.deduplication import DeduplicationService

    publisher = Publisher(name="Wire", domain="a.example", publisher_type=PublisherType.NEWS.value)
    session.add(publisher)
    session.flush()
    first = Document(url="https://a.example/x", title="A", canonical_url="https://a.example/x", publisher_id=publisher.id)
    second = Document(url="https://b.example/y", title="B", canonical_url="https://b.example/y", publisher_id=publisher.id)
    session.add_all([first, second])
    session.flush()

    DeduplicationService.create_obvious_relationships(
        session, first, second, SourceRelationshipType.COPIED_FROM.value, "Same body text."
    )
    session.commit()
    # Recording the identical edge a second time must be a no-op, not an error.
    DeduplicationService.create_obvious_relationships(
        session, first, second, SourceRelationshipType.COPIED_FROM.value, "Same body text."
    )
    session.commit()

    from app.models import SourceRelationship

    assert session.query(SourceRelationship).count() == 1


def test_legacy_report_with_null_primary_status_still_loads(session: Session, client: TestClient) -> None:
    """Reports written before the column was populated must still be readable.

    `reports.primary_evidence_status` is nullable, and the response schema types
    it as a plain string, so passing None through fails validation and turns
    every such investigation into a 500.
    """
    claim = Claim(claim_text="An older claim.")
    subclaim = Subclaim(claim=claim, text="An older claim.", subclaim_type=SubclaimType.FACTUAL.value)
    session.add_all([claim, subclaim])
    session.flush()
    session.add(
        Report(
            claim_id=claim.id,
            report_text="A report written before the column existed.",
            primary_evidence_status=None,
        )
    )
    session.commit()

    response = client.get(f"/api/v1/investigations/{claim.id}")

    assert response.status_code == 200
    assert response.json()["primary_evidence_status"] == "NOT_SEARCHED"


def test_evidence_exposes_document_provenance(session: Session, client: TestClient) -> None:
    """Evidence must carry the source details a reader needs to follow the link."""
    claim = Claim(claim_text="A claim with provenance.")
    subclaim = Subclaim(claim=claim, text="A claim.", subclaim_type=SubclaimType.FACTUAL.value)
    publisher = Publisher(name="Wire", domain="wire.example", publisher_type=PublisherType.NEWS.value)
    session.add_all([claim, subclaim, publisher])
    session.flush()

    document = Document(
        publisher_id=publisher.id,
        url="https://wire.example/story",
        canonical_url="https://wire.example/story",
        title="The original headline",
        source_type=DocumentSourceType.NEWS,
    )
    session.add(document)
    session.flush()

    item = EvidenceItem(
        claim_id=claim.id,
        subclaim_id=subclaim.id,
        document_id=document.id,
        stance=EvidenceStance.SUPPORTS,
        summary="The document entails the claim.",
        url=document.url,
        retrieval_channel="gdelt",
        raw_excerpt="An excerpt from the article body.",
    )
    session.add(item)
    session.commit()

    evidence = client.get(f"/api/v1/investigations/{claim.id}").json()["evidence"]

    assert len(evidence) == 1
    payload = evidence[0]
    assert payload["title"] == "The original headline"
    assert payload["publisher"] == "Wire"
    assert payload["publisher_domain"] == "wire.example"
    assert payload["retrieval_channel"] == "gdelt"
    assert payload["excerpt"] == "An excerpt from the article body."
    assert payload["source_type"] == "news"
    assert payload["assessment_status"] == "unassessed"


def test_conclusive_verdicts_mark_the_claim_verified() -> None:
    """Verification emits SCREAMING_SNAKE verdicts; casing must not hide them."""
    for verdict in ("DISPUTED", "SUPPORTED", "misleading_or_incomplete", "Partially_Supported"):
        assert InvestigationGraph._status_for(verdict) == ClaimStatus.VERIFIED.value
    for verdict in ("", "INSUFFICIENT_EVIDENCE", None):
        assert InvestigationGraph._status_for(verdict) == ClaimStatus.ANALYZING.value


# ----------------------------------------------------------------------
# LLM client
# ----------------------------------------------------------------------
def test_llm_client_never_fabricates_structured_output() -> None:
    from app.services.llm import LLMClient, LLMUnavailableError

    with patch("app.services.llm.settings.GEMINI_API_KEY", ""), patch(
        "app.services.llm.settings.GOOGLE_API_KEY", ""
    ), patch("app.services.llm.settings.OPENAI_API_KEY", None):
        client = LLMClient()
        assert client.is_configured() is False
        with pytest.raises(LLMUnavailableError):
            client.generate_structured(PropositionSchema, "prompt")


def test_llm_client_reports_the_provider_error() -> None:
    from app.services.llm import LLMClient, LLMUnavailableError

    with patch("app.services.llm.settings.GEMINI_API_KEY", "key"), patch("app.services.llm.settings.GOOGLE_API_KEY", None):
        client = LLMClient()
        with patch.object(client, "_dispatch", side_effect=Exception("boom")):
            with pytest.raises(LLMUnavailableError):
                client.generate("prompt")
        assert "boom" in (client.last_error or "")


# ----------------------------------------------------------------------
# Completeness and media analysis
# ----------------------------------------------------------------------
def test_completeness_uses_the_model_when_available() -> None:
    from app.agents.completeness import CompletenessSchema

    with patch("app.agents.completeness.LLMClient.generate_structured") as generate:
        generate.return_value = CompletenessSchema(
            completeness_status="MISLEADING_BY_OMISSION",
            missing_context=["No comparison period was provided."],
            qualifications=["A baseline is required to interpret the claim."],
            explanation="The claim omits the comparison period.",
            confidence=0.82,
        )
        result = CompletenessAgent().analyze(
            "A causal claim.", evidence_items=[Mock(summary="x")], subclaims=[Mock(text="y")]
        )
    generate.assert_called_once()
    assert result["completeness_status"] == "MISLEADING_BY_OMISSION"


def test_completeness_falls_back_to_structural_checks() -> None:
    with patch("app.agents.completeness.LLMClient.generate_structured", side_effect=LLMUnavailableError("x")):
        result = CompletenessAgent().analyze(
            "The policy caused spending to rise.", evidence_items=[], subclaims=[]
        )
    assert result["completeness_status"] in {"MOSTLY_COMPLETE", "MISLEADING_BY_OMISSION", "INCOMPLETE"}
    assert result["missing_context"]


def test_completeness_rejects_an_unknown_status_from_the_model() -> None:
    from app.agents.completeness import CompletenessSchema

    with patch("app.agents.completeness.LLMClient.generate_structured") as generate:
        generate.return_value = CompletenessSchema(completeness_status="TOTALLY_FINE")
        result = CompletenessAgent().analyze("A claim.", evidence_items=[], subclaims=[])
    assert result["completeness_status"] == "MOSTLY_COMPLETE"


def test_media_analysis_is_isolated_from_verification() -> None:
    with patch("app.agents.media_analysis.LLMClient.generate_structured", side_effect=LLMUnavailableError("x")):
        media = MediaAnalysisAgent().analyze(
            "The policy caused spending to rise.",
            documents=[Mock(publisher=Mock(name="Reuters")), Mock(publisher=Mock(name="Fox News"))],
            evidence_items=[Mock(stance="supports"), Mock(stance="contradicts")],
        )
    assert "framing_summary" in media
    assert "misleading" not in str(media["framing_summary"]).lower()
    assert media["publisher_distribution"]["Reuters"] >= 1


def test_media_analysis_does_not_treat_orientation_as_evidence() -> None:
    with patch("app.agents.media_analysis.LLMClient.generate_structured", side_effect=LLMUnavailableError("x")):
        media = MediaAnalysisAgent().analyze(
            "A claim.",
            documents=[Mock(publisher=Mock(name="BBC")), Mock(publisher=Mock(name="MSNBC"))],
            evidence_items=[],
        )
    assert media["center_coverage"] > 0
    assert media["left_coverage"] > 0
    assert "does not indicate whether the claim is true" in media["omitted_context"]


# ----------------------------------------------------------------------
# Writer
# ----------------------------------------------------------------------
def test_writer_preserves_the_verdict_and_reports_primary_status() -> None:
    with patch("app.agents.writer.LLMClient.is_configured", return_value=False):
        report = WriterAgent().write(
            "The policy caused spending to rise.",
            [Mock(id=1, text="The policy caused spending to rise.")],
            {"overall_verdict": "PARTIALLY_SUPPORTED", "overall_confidence": 0.74, "explanation": "Mixed evidence."},
            {"completeness_status": "MOSTLY_COMPLETE", "missing_context": [], "qualifications": []},
            [
                Mock(
                    subclaim_id=1,
                    stance=EvidenceStance.SUPPORTS,
                    url="https://example.com/support",
                    summary="Supporting document.",
                ),
                Mock(
                    subclaim_id=1,
                    stance=EvidenceStance.CONTEXT,
                    url="https://example.com/context",
                    summary="Related document.",
                ),
            ],
            [Mock(title="A report", url="https://example.com/support")],
            {"framing_summary": "Coverage summary."},
            {"documents_found": 2, "distinct_publishers": 2, "independent_groups": 2},
            [{"subclaim_id": 1, "verdict": "PARTIALLY_SUPPORTED", "confidence": 0.74, "rationale": "Mixed evidence."}],
            primary_status="NOT_CONFIGURED",
        )
    assert "PARTIALLY_SUPPORTED" in report.upper()
    assert "Mixed evidence." in report
    # The primary evidence line must show the real primary status, not a completeness value.
    assert "Primary/authoritative evidence: NOT_CONFIGURED" in report
    assert "Context only" in report


def test_writer_does_not_invent_evidence_when_the_model_is_unavailable() -> None:
    with patch("app.agents.writer.LLMClient.is_configured", return_value=True), patch(
        "app.agents.writer.LLMClient.generate", side_effect=LLMUnavailableError("x")
    ):
        report = WriterAgent().write(
            "A claim.",
            [Mock(id=1, text="A claim.")],
            {"overall_verdict": "INSUFFICIENT_EVIDENCE", "overall_confidence": 0.2, "explanation": "Thin evidence."},
            {"completeness_status": "MOSTLY_COMPLETE", "missing_context": [], "qualifications": []},
            [Mock(subclaim_id=1, stance=EvidenceStance.CONTEXT, url=None, summary="Related.")],
            [],
            {},
            {"documents_found": 1},
            [{"subclaim_id": 1, "verdict": "INSUFFICIENT_EVIDENCE", "confidence": 0.2, "rationale": "Thin."}],
            primary_status="NOT_FOUND",
        )
    assert "Thin evidence." in report
    assert "Supporting evidence" in report
    assert "None identified." in report


# ----------------------------------------------------------------------
# Pipeline
# ----------------------------------------------------------------------
def test_pipeline_records_a_verified_conclusion_separate_from_raw_evidence(session: Session) -> None:
    engine = _scripted(
        "supports",
        [
            {"dimension": "subject", "status": "match", "evidence_value": "s", "note": ""},
            {"dimension": "action", "status": "match", "evidence_value": "a", "note": ""},
        ],
        0.8,
    )
    documents = [
        {
            "title": "A report",
            "url": "https://one.example/story",
            "publisher": "Outlet One",
            "content": "The report body.",
            "retrieval_channel": "gdelt",
        },
        {
            "title": "Another report",
            "url": "https://two.example/story",
            "publisher": "Outlet Two",
            "content": "A different report body entirely.",
            "retrieval_channel": "gdelt",
        },
    ]
    retriever = Mock(channel_name="gdelt")
    retriever.search.return_value = documents
    broken = Mock(channel_name="broken")
    broken.search.side_effect = RuntimeError("channel failed")

    graph = InvestigationGraph(session_factory=lambda: session, engine=engine)
    with _offline_llm(), patch(
        "app.services.deduplication.DeduplicationService._classify_pair", return_value=(None, "", 0.0)
    ):
        result = graph.run_investigation(
            "The council approved the budget in 2024.", retrievers=[broken, retriever], session=session
        )

    assert result["status"] == "completed"
    assert result["claim_id"] is not None
    assert result["subclaims"]

    from app.models import SubclaimConclusion, VerificationVerdict

    conclusions = session.query(SubclaimConclusion).all()
    assert conclusions
    for conclusion in conclusions:
        assert conclusion.verdict in {member.value for member in VerificationVerdict}
        assert conclusion.independent_source_groups >= 0

    # A retrieved document is not automatically an evidence item.
    assert result["evidence_count"] <= len(result["documents"]) * len(result["subclaims"])
    assert result["retrieval_stats"]["raw_documents"] >= 0


def test_pipeline_survives_a_failing_channel_and_continues(session: Session) -> None:
    engine = _scripted("context", [], 0.2)
    retriever = Mock(channel_name="gdelt")
    retriever.search.return_value = [
        {"title": "A report", "url": "https://one.example/a", "publisher": "One", "content": "Body."}
    ]
    broken = Mock(channel_name="broken")
    broken.search.side_effect = RuntimeError("down")

    graph = InvestigationGraph(session_factory=lambda: session, engine=engine)
    with _offline_llm():
        result = graph.run_investigation("A claim about a local decision.", retrievers=[broken, retriever], session=session)

    assert result["status"] == "completed"
    assert result["claim_id"] is not None


def test_claim_status_is_not_marked_verified_without_a_conclusive_verdict(session: Session) -> None:
    engine = _scripted("context", [], 0.2)
    retriever = Mock(channel_name="gdelt")
    retriever.search.return_value = []

    graph = InvestigationGraph(session_factory=lambda: session, engine=engine)
    with _offline_llm():
        result = graph.run_investigation("An unsupported claim.", retrievers=[retriever], session=session)

    claim = session.get(Claim, result["claim_id"])
    assert claim.status != ClaimStatus.VERIFIED.value


# ----------------------------------------------------------------------
# API
# ----------------------------------------------------------------------
@pytest.fixture
def client(session: Session) -> TestClient:
    app.dependency_overrides[get_db] = lambda: session
    return TestClient(app)


def test_investigation_api_create_and_get(client: TestClient) -> None:
    engine = _scripted(
        "contradicts",
        [
            {"dimension": "subject", "status": "match", "evidence_value": "s", "note": ""},
            {"dimension": "action", "status": "match", "evidence_value": "a", "note": ""},
            {"dimension": "date_time", "status": "conflict", "evidence_value": "a different date", "note": ""},
        ],
        0.8,
    )
    retriever = Mock(channel_name="gdelt")
    retriever.search.return_value = [
        {"title": "A report", "url": "https://one.example/a", "publisher": "One", "content": "Body text."}
    ]

    with _offline_llm(), patch(
        "app.graph.investigation.InvestigationGraph._default_retrievers", return_value=[retriever]
    ), patch(
        "app.services.entailment.EntailmentEngine.assess",
        side_effect=lambda proposition, text, title="": engine.assess(proposition, text, title),
    ):
        response = client.post(
            "/api/v1/investigations",
            json={"claim": "The city reduced traffic by 20% after the new lane opened."},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    claim_id = payload["claim_id"]

    detail = client.get(f"/api/v1/investigations/{claim_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["claim_id"] == claim_id
    assert data["subclaims"]
    assert data["report"]
    assert data["verification"]
    assert data["primary_evidence_status"]


def test_investigation_api_returns_404_for_unknown_claim(client: TestClient) -> None:
    assert client.get("/api/v1/investigations/999999").status_code == 404


def test_investigation_api_rejects_an_empty_claim(client: TestClient) -> None:
    assert client.post("/api/v1/investigations", json={"claim": ""}).status_code == 422
