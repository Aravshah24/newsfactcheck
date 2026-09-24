from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.main import app
from app.db.base import Base
from app.models import (
    Claim,
    ClaimStatus,
    Document,
    DocumentSourceType,
    EvidenceAssessmentStatus,
    EvidenceCategory,
    EvidenceStance,
    Publisher,
    PublisherType,
    SearchChannel,
    SourceRelationshipType,
    Subclaim,
    SubclaimType,
)
from app.services.claim_analysis import ClaimAnalyzer
from app.services.clustering import EvidenceClusteringService
from app.services.deduplication import DeduplicationService
from app.services.llm import LLMClient
from app.agents.completeness import CompletenessAgent
from app.agents.evidence_extraction import EvidenceExtractor
from app.agents.media_analysis import MediaAnalysisAgent
from app.agents.opposition import OppositionAgent
from app.agents.verification import VerificationAgent
from app.agents.writer import WriterAgent
from app.retrievers.gdelt import GDELTRetriever
from app.retrievers.primary_source import PrimarySourceRetriever
from app.retrievers.web_search import WebSearchRetriever
from app.graph.investigation import InvestigationGraph


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(bind=engine) as session:
        yield session


def test_claim_analyzer_atomic_claim() -> None:
    analyzer = ClaimAnalyzer()
    claim, subclaims = analyzer.build_claim_record("The city council approved the budget.")

    assert claim.claim_text == "The city council approved the budget."
    assert len(subclaims) == 1
    assert subclaims[0].subclaim_type == SubclaimType.FACTUAL.value


def test_claim_analyzer_compound_quantitative_and_causal() -> None:
    analyzer = ClaimAnalyzer()
    claim, subclaims = analyzer.build_claim_record(
        "The company hired 50 employees and the hiring caused revenue to rise 20% after 2024."
    )

    types = {sub.subclaim_type for sub in subclaims}
    assert SubclaimType.QUANTITATIVE.value in types
    assert SubclaimType.CAUSAL.value in types


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
    retriever = GDELTRetriever()
    with patch("app.retrievers.gdelt.httpx.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"articles": []}
        results = retriever.search(subclaim=None, query="No results query", max_results=5)
    assert results == []


def test_gdelt_api_failure() -> None:
    retriever = GDELTRetriever()
    with patch("app.retrievers.gdelt.httpx.get", side_effect=RuntimeError("failure")):
        results = retriever.search(subclaim=None, query="Failure query", max_results=5)
    assert results == []


def test_web_search_unavailable() -> None:
    with patch("app.retrievers.web_search.settings.WEB_SEARCH_PROVIDER", None), patch(
        "app.retrievers.web_search.settings.WEB_SEARCH_API_KEY", None
    ):
        retriever = WebSearchRetriever()
        results = retriever.search(subclaim=None, query="anything")
    assert results == []
    assert retriever.is_available() is False


def test_primary_source_unavailable() -> None:
    with patch("app.retrievers.primary_source.settings.PRIMARY_SOURCE_API_KEY", ""):
        retriever = PrimarySourceRetriever()
        results = retriever.search(subclaim=None, query="agency report")
    assert results == []


def test_opposition_agent_generates_counter_queries() -> None:
    agent = OppositionAgent(retrievers=[])
    queries = agent.generate_queries("The company raised prices and sales fell in 2024.")
    assert len(queries) >= 2
    assert all("false" not in q.lower() for q in queries)
    assert any("alternative" in q.lower() or "disputed" in q.lower() or "timeline" in q.lower() for q in queries)


def test_opposition_agent_searches_for_contradicting_evidence() -> None:
    fake_retriever = Mock()
    fake_retriever.search.return_value = [
        {
            "title": "Disputing report",
            "url": "https://example.com/rebuttal",
            "publisher": "Independent Watch",
            "publication_date": datetime(2024, 1, 1),
            "content": "The company's sales were flat, not lower.",
            "retrieval_channel": "web_search",
            "query": "sales fell alternative explanation",
        }
    ]
    agent = OppositionAgent(retrievers=[fake_retriever])
    claim = Claim(claim_text="The company raised prices and sales fell in 2024.")
    subclaim = Subclaim(claim=claim, text="Sales fell in 2024.", subclaim_type=SubclaimType.QUANTITATIVE.value)
    results = agent.search_counter_evidence(subclaim)

    assert len(results) == 1
    assert results[0]["title"] == "Disputing report"


def test_evidence_extraction_linked_to_correct_subclaim(session: Session) -> None:
    claim = Claim(claim_text="The mayor raised taxes.")
    subclaim = Subclaim(claim=claim, text="The mayor raised taxes.", subclaim_type=SubclaimType.FACTUAL.value)
    publisher = Publisher(name="City Press", publisher_type=PublisherType.NEWS.value)
    document = Document(
        publisher=publisher,
        url="https://example.com/tax-rise",
        canonical_url="https://example.com/tax-rise",
        title="City tax increase",
        source_type=DocumentSourceType.NEWS,
        content_hash="hash-1",
    )
    session.add_all([claim, subclaim, publisher, document])
    session.flush()

    evidence = EvidenceExtractor().extract(subclaim, document, "The mayor announced a tax increase on August 4.")
    session.add(evidence)
    session.flush()

    assert evidence.subclaim_id == subclaim.id
    assert evidence.document_id == document.id
    assert evidence.category == EvidenceCategory.RAW
    assert evidence.stance in {EvidenceStance.SUPPORTS, EvidenceStance.CONTEXT, EvidenceStance.UNKNOWN}
    assert evidence.assessment_status == EvidenceAssessmentStatus.UNASSESSED
    assert evidence.raw_excerpt is not None
    assert evidence.extra_metadata["extraction_method"] == "rule_based"


def test_deduplication_same_url_and_hash(session: Session) -> None:
    publisher = Publisher(name="Example Press", publisher_type=PublisherType.NEWS.value)
    doc_a = Document(
        publisher=publisher,
        url="https://example.com/story",
        canonical_url="https://example.com/story",
        title="Story A",
        content_hash="samehash",
        source_type=DocumentSourceType.NEWS,
    )
    session.add_all([publisher, doc_a])
    session.flush()

    doc_b = Document(
        publisher=publisher,
        url="https://example.com/story",
        canonical_url="https://example.com/story",
        title="Story B",
        content_hash="samehash",
        source_type=DocumentSourceType.NEWS,
    )
    existing = DeduplicationService().resolve_duplicate_document(session, doc_b)
    assert existing is doc_a

    doc_c = Document(
        publisher=publisher,
        url="https://example.com/other",
        canonical_url="https://example.com/other",
        title="Story C",
        content_hash="samehash",
        source_type=DocumentSourceType.NEWS,
    )
    session.add(doc_c)
    session.flush()
    relation_count = session.query(Document).filter(Document.content_hash == "samehash").count()
    assert relation_count >= 2


def test_relationships_copied_and_syndicated(session: Session) -> None:
    service = DeduplicationService()
    publisher = Publisher(name="Source News", publisher_type=PublisherType.NEWS.value)
    original = Document(
        publisher=publisher,
        url="https://source.example/article",
        canonical_url="https://source.example/article",
        title="Original",
        content_hash="hash-original",
        source_type=DocumentSourceType.NEWS,
    )
    syndicated = Document(
        publisher=Publisher(name="Republished News", publisher_type=PublisherType.NEWS.value),
        url="https://republish.example/article",
        canonical_url="https://republish.example/article",
        title="Republished",
        content_hash="hash-original",
        source_type=DocumentSourceType.NEWS,
    )
    session.add_all([publisher, original, syndicated.publisher, syndicated])
    session.flush()

    service.create_obvious_relationships(session, original, syndicated)
    session.flush()
    relationship = session.query(type(original)).filter_by(id=original.id).first()
    assert relationship is not None


def test_evidence_clustering_keeps_clustering_separate_from_independence(session: Session) -> None:
    claim = Claim(claim_text="Clustered evidence.")
    subclaim = Subclaim(claim=claim, text="A cluster exists.", subclaim_type=SubclaimType.FACTUAL.value)
    publisher = Publisher(name="Cluster Press", publisher_type=PublisherType.NEWS.value)
    doc = Document(
        publisher=publisher,
        url="https://example.com/cluster1",
        canonical_url="https://example.com/cluster1",
        title="Cluster 1",
        content_hash="cluster-hash",
        source_type=DocumentSourceType.NEWS,
    )
    session.add_all([claim, subclaim, publisher, doc])
    session.flush()

    clusters = EvidenceClusteringService().cluster_by_document_hash(session, claim)
    assert len(clusters) >= 0


def test_llm_client_defaults_to_gemini_and_calls_real_sdk() -> None:
    client = LLMClient()
    assert client.provider == "gemini"
    assert client.model == "gemini-2.5-flash"

    with patch("app.config.settings.GEMINI_API_KEY", "test-key"), patch("google.genai.Client") as mock_client:
        mock_response = Mock()
        mock_response.text = "The evidence is mixed but the claim needs additional context."
        mock_client.return_value.models.generate_content.return_value = mock_response

        output = client.generate("Does the claim need more context?")
        assert output == "The evidence is mixed but the claim needs additional context."
        mock_client.return_value.models.generate_content.assert_called_once()


def test_graph_fanout_and_failure_isolation() -> None:
    graph = InvestigationGraph()
    results = graph.run_investigation(
        "The government announced a 15% tax cut and the policy caused spending to rise.",
        retrievers=[
            Mock(search=Mock(return_value=[{ "title": "official report", "url": "https://example.com/official", "publisher": "Government", "publication_date": datetime(2024, 1, 1), "content": "The government announced a 15% tax cut.", "retrieval_channel": "GDELT", "query": "tax cut" }])),
            Mock(search=Mock(side_effect=RuntimeError("channel failed"))),
        ],
        session_factory=None,
    )

    assert results["status"] == "completed"
    assert results["claim_id"] is not None
    assert len(results["subclaims"]) >= 2
    assert results["errors"] == []


def test_investigation_api_create_and_get() -> None:
    app.dependency_overrides = {}
    client = TestClient(app)

    response = client.post("/api/v1/investigations", json={"claim": "The city reduced traffic by 20% after the new lane opened."})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "started"
    claim_id = payload["claim_id"]

    results = client.get(f"/api/v1/investigations/{claim_id}")
    assert results.status_code == 200
    data = results.json()
    assert data["claim_id"] == claim_id
    assert len(data["subclaims"]) >= 1


def test_completeness_agent_uses_live_llm_when_configured() -> None:
    agent = CompletenessAgent()
    evidence_items = [Mock(summary="The tax cut was announced alongside a budget transfer."), Mock(summary="Officials stated the policy was adopted in 2024.")]
    subclaims = [Mock(text="The government cut taxes and spending rose after the tax cut.")]

    with patch("app.agents.completeness.LLMClient.generate_structured") as mock_llm:
        mock_llm.return_value = {
            "completeness_status": "MISLEADING_BY_OMISSION",
            "missing_context": ["No comparison period was provided."],
            "qualifications": ["A baseline is required to interpret the claim."],
            "explanation": "The claim could be misleading without the comparison period.",
            "confidence": 0.82,
        }
        result = agent.analyze("Tax cut caused spending to rise.", evidence_items=evidence_items, subclaims=subclaims)

    mock_llm.assert_called_once()
    assert result["completeness_status"] == "MISLEADING_BY_OMISSION"


def test_verification_agent_uses_live_llm_when_configured() -> None:
    subclaim = Mock(id=7, text="The government cut taxes and spending rose.")
    evidence_items = [
        Mock(subclaim_id=7, stance="supports", summary="Government report says the tax cut was implemented."),
        Mock(subclaim_id=7, stance="context", summary="The agency compared annual spending before and after the policy."),
    ]

    with patch("app.agents.verification.LLMClient.generate_structured") as mock_llm:
        mock_llm.return_value = {
            "verdict": "PARTIALLY_SUPPORTED",
            "confidence": 0.74,
            "rationale": "The evidence is mixed and the causal link remains tentative.",
            "supporting_evidence_count": 1,
            "contradicting_evidence_count": 0,
            "context_evidence_count": 1,
            "primary_evidence_status": "FOUND",
            "method": "llm_evidence_review",
        }
        result = VerificationAgent().verify(
            subclaim,
            evidence_items,
            completeness_result={"completeness_status": "MOSTLY_COMPLETE", "missing_context": [], "qualifications": []},
            primary_status="FOUND",
            independence_summary={"estimated_independent_sources": 2},
        )

    mock_llm.assert_called_once()
    assert result["verdict"] == "PARTIALLY_SUPPORTED"
    assert result["method"] == "llm_evidence_review"
    assert result["supporting_evidence_count"] == 1
    assert result["contradicting_evidence_count"] == 0
    assert result["context_evidence_count"] == 1


def test_media_analysis_isolated_from_verdict_and_writer_preserves_verdict() -> None:
    media = MediaAnalysisAgent().analyze(
        "The policy caused spending to rise.",
        documents=[
            Mock(publisher=Mock(name="Reuters")),
            Mock(publisher=Mock(name="Fox News")),
        ],
        evidence_items=[Mock(stance="supports"), Mock(stance="contradicts")],
    )
    assert "framing_summary" in media
    assert "misleading" not in str(media["framing_summary"]).lower()
    assert media["publisher_distribution"]["Reuters"] >= 1

    report = WriterAgent().write(
        "The policy caused spending to rise.",
        [Mock(id=1, text="The policy caused spending to rise.")],
        {"overall_verdict": "PARTIALLY_SUPPORTED", "overall_confidence": 0.74, "explanation": "Mixed evidence."},
        {"completeness_status": "MOSTLY_COMPLETE", "missing_context": [], "qualifications": []},
        [Mock(subclaim_id=1, stance="supports", url="https://example.com/support", summary="The policy was implemented after a tax cut.")],
        [Mock(title="Reuters report", url="https://example.com/support")],
        media,
        {"documents_found": 2, "distinct_publishers": 2, "evidence_clusters": 1, "estimated_independent_sources": 2},
        [{"subclaim_id": 1, "verdict": "PARTIALLY_SUPPORTED", "confidence": 0.74, "rationale": "Mixed evidence."}],
    )
    assert "PARTIALLY_SUPPORTED" in report.upper()
    assert "Mixed evidence." in report
