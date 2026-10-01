from __future__ import annotations

"""Regression tests for the propositional evidence layer.

These tests assert the conceptual contract of the system:

    RETRIEVED DOCUMENT != EVIDENCE != SUPPORTING EVIDENCE

They deliberately avoid asserting on any specific entity, event, or location, so
that the behaviour must hold through general proposition-level reasoning rather
than through hardcoded rules.
"""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agents.evidence_extraction import EvidenceExtractor
from app.agents.verification import VerificationAgent
from app.db.base import Base
from app.services.deduplication import DeduplicationService
from app.services.entailment import (
    DimensionComparison,
    EntailmentEngine,
    EntailmentResult,
    EntailmentSchema,
    MultiDocumentEntailmentItem,
    MultiDocumentEntailmentSchema,
)
from app.services.evidence_stance import normalise_stance
from app.services.independence import IndependenceAnalyzer
from app.services.llm import LLMUnavailableError
from app.services.proposition import (
    BatchedPropositionItem,
    BatchedPropositionSchema,
    Proposition,
    PropositionExtractor,
    PropositionSchema,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(bind=engine) as db:
        yield db


# ----------------------------------------------------------------------
# Fakes
# ----------------------------------------------------------------------
class ScriptedEngine(EntailmentEngine):
    """Returns a canned comparison so guard-rail behaviour can be tested offline."""

    def __init__(self, response):
        self.response = response
        self.asked: list[str] = []
        self._proposition_cache: dict[str, Proposition] = {}

    def proposition_for(self, claim_text: str) -> Proposition:
        self.asked.append(claim_text)
        return Proposition(claim_text, {"subject": "s", "action": "a", "object": "o"}, degraded=False)

    def preload_propositions(self, claim_texts: list[str]) -> dict[str, Proposition]:
        return {}

    def assess(self, proposition, evidence_text, document_title="") -> EntailmentResult:
        comparisons = self.response.get("dimensions", [])
        status = {item.dimension: item.status for item in comparisons}
        conflicts = {
            item.dimension: (item.evidence_value or item.note or "")
            for item in comparisons
            if item.status == "conflict"
        }
        return EntailmentResult(
            stance=self.response["stance"],
            confidence=self.response.get("confidence", 0.5),
            rationale=self.response.get("rationale", "scripted"),
            dimension_status=status,
            dimension_conflicts=conflicts,
            method="scripted",
        )

    def assess_many(self, propositions, evidence_text, document_title="") -> list[EntailmentResult]:
        return [self.assess(proposition, evidence_text, document_title) for proposition in propositions]


class FakeDocument:
    def __init__(self, doc_id=1, text="", title="Untitled", url="https://example.com/a"):
        self.id = doc_id
        self.text_content = text
        self.title = title
        self.url = url


class FakeSubclaim:
    def __init__(self, subclaim_id=1, claim_id=1, text="The proposition."):
        self.id = subclaim_id
        self.claim_id = claim_id
        self.text = text


# ----------------------------------------------------------------------
# Proposition extraction
# ----------------------------------------------------------------------
def test_proposition_fallback_is_marked_degraded_and_never_invents_a_subject() -> None:
    proposition = PropositionExtractor._fallback("The council cut the fee by 15% in 2024.")
    assert proposition.degraded is True
    # A degraded proposition must not claim to have resolved subject/action/object.
    assert proposition.value("subject") == ""
    assert proposition.value("action") == ""
    # Generic surface cues are still recovered.
    assert "15%" in str(proposition.value("quantity"))
    assert "2024" in str(proposition.value("date_time"))


def test_proposition_fallback_detects_negation_generically() -> None:
    assert PropositionExtractor._fallback("The council did not cut the fee.").value("polarity") == "negative"
    assert PropositionExtractor._fallback("The council cut the fee.").value("polarity") == "affirmative"


def test_proposition_extraction_uses_the_model_when_available() -> None:
    with patch("app.services.proposition.LLMClient.generate_structured") as generate:
        generate.return_value = PropositionSchema(
            subject="the council",
            action="cut",
            object="the fee",
            date_time="2024",
            quantity="15%",
            polarity="affirmative",
            qualifiers=[],
            is_atomic=True,
        )
        proposition = PropositionExtractor().extract("The council cut the fee by 15% in 2024.")
    generate.assert_called_once()
    assert proposition.degraded is False
    assert proposition.value("subject") == "the council"
    assert proposition.value("quantity") == "15%"


def test_proposition_extraction_degrades_when_the_model_is_unavailable() -> None:
    with patch("app.services.proposition.LLMClient.generate_structured", side_effect=LLMUnavailableError("down")):
        proposition = PropositionExtractor().extract("The council cut the fee by 15% in 2024.")
    assert proposition.degraded is True


# ----------------------------------------------------------------------
# Entailment guard rails
# ----------------------------------------------------------------------
def _comparison(dimension: str, status: str, value: str = "") -> DimensionComparison:
    return DimensionComparison(dimension=dimension, status=status, evidence_value=value, note="")


def test_any_conflicting_dimension_forces_contradiction() -> None:
    engine = EntailmentEngine()
    schema = EntailmentSchema(
        stance="supports",
        dimensions=[
            _comparison("subject", "match"),
            _comparison("action", "match"),
            _comparison("object", "conflict", "a different object"),
        ],
        confidence=0.95,
    )
    result = engine._reconcile(
        Proposition("c", {"subject": "s", "action": "a", "object": "o"}), schema
    )
    assert result.stance == "contradicts"
    assert "object" in result.dimension_conflicts


def test_support_is_refused_when_a_specified_dimension_is_not_matched() -> None:
    engine = EntailmentEngine()
    schema = EntailmentSchema(
        stance="supports",
        dimensions=[
            _comparison("subject", "match"),
            _comparison("action", "match"),
            _comparison("date_time", "absent"),
        ],
        confidence=0.95,
    )
    result = engine._reconcile(
        Proposition("c", {"subject": "s", "action": "a", "date_time": "2024"}), schema
    )
    assert result.stance == "context"
    assert "date_time" in result.rationale


def test_support_is_upheld_when_every_specified_dimension_matches() -> None:
    engine = EntailmentEngine()
    schema = EntailmentSchema(
        stance="supports",
        dimensions=[_comparison("subject", "match"), _comparison("action", "match")],
        confidence=0.8,
    )
    result = engine._reconcile(Proposition("c", {"subject": "s", "action": "a"}), schema)
    assert result.stance == "supports"


def test_model_cannot_claim_support_over_a_reported_conflict() -> None:
    """The guard rail must win even when the model returns a confident 'supports'."""
    engine = EntailmentEngine()
    schema = EntailmentSchema(
        stance="supports",
        dimensions=[_comparison("quantity", "conflict", "a different quantity")],
        confidence=0.99,
    )
    result = engine._reconcile(Proposition("c", {"subject": "s", "action": "a", "quantity": "10"}), schema)
    assert result.stance == "contradicts"


def test_entailment_falls_back_to_context_when_the_model_is_unavailable() -> None:
    engine = EntailmentEngine()
    proposition = Proposition("c", {"subject": "s", "action": "a"}, degraded=False)
    with patch.object(engine.llm, "generate_structured", side_effect=LLMUnavailableError("down")):
        result = engine.assess(proposition, "Some document text about the same topic.")
    # Without a model we must never manufacture support.
    assert result.stance == "context"
    assert result.method == "llm_unavailable"


# ----------------------------------------------------------------------
# Batching
# ----------------------------------------------------------------------
def test_one_call_covers_every_claim_for_a_document() -> None:
    """Providers meter per request, so a document must cost one call, not one per claim."""
    engine = EntailmentEngine()
    propositions = [Proposition(f"claim {index}", {"subject": "s", "action": "a"}) for index in range(4)]

    response = MultiDocumentEntailmentSchema(
        results=[
            MultiDocumentEntailmentItem(
                document_index=0, claim_index=index, stance="context", confidence=0.4, rationale=f"claim {index}"
            )
            for index in range(4)
        ]
    )
    with patch.object(engine.llm, "generate_structured", return_value=response) as generate:
        results = engine.assess_many(propositions, "Document text.", "Title")

    generate.assert_called_once()
    assert len(results) == 4
    assert all(result.stance == "context" for result in results)


def test_documents_are_assessed_in_groups() -> None:
    engine = EntailmentEngine()
    propositions = [Proposition("claim", {"subject": "s", "action": "a"})]
    documents = [(f"doc {index}", f"Body of document {index}.") for index in range(5)]

    with patch("app.services.entailment.settings.EVIDENCE_DOCUMENT_BATCH_SIZE", 2), patch.object(
        engine.llm, "generate_structured", return_value=MultiDocumentEntailmentSchema(results=[])
    ) as generate:
        rows = engine.assess_documents(propositions, documents)

    # Five documents in groups of two costs three calls, not five.
    assert generate.call_count == 3
    assert len(rows) == 5
    assert all(len(row) == 1 for row in rows)


def test_a_pair_omitted_from_the_response_is_never_treated_as_support() -> None:
    engine = EntailmentEngine()
    propositions = [Proposition("claim a", {"subject": "s", "action": "a"}), Proposition("claim b", {"subject": "s"})]
    response = MultiDocumentEntailmentSchema(
        results=[
            MultiDocumentEntailmentItem(
                document_index=0, claim_index=0, stance="supports", confidence=0.9, rationale="ok"
            )
        ]
    )
    with patch.object(engine.llm, "generate_structured", return_value=response):
        results = engine.assess_many(propositions, "Document text.", "Title")

    assert len(results) == 2
    assert results[1].stance == "context"
    assert results[1].method == "pair_omitted_from_response"


def test_batched_proposition_extraction_returns_one_proposition_per_statement() -> None:
    texts = ["A first statement.", "A second statement."]
    response = BatchedPropositionSchema(
        items=[
            BatchedPropositionItem(index=0, subject="s1", action="a1"),
            BatchedPropositionItem(index=1, subject="s2", action="a2"),
        ]
    )
    with patch("app.services.proposition.LLMClient.generate_structured", return_value=response) as generate:
        propositions = PropositionExtractor().extract_many(texts)

    generate.assert_called_once()
    assert [proposition.value("subject") for proposition in propositions] == ["s1", "s2"]
    assert all(not proposition.degraded for proposition in propositions)


def test_proposition_extraction_degrades_when_a_statement_is_omitted() -> None:
    response = BatchedPropositionSchema(items=[BatchedPropositionItem(index=0, subject="s1")])
    with patch("app.services.proposition.LLMClient.generate_structured", return_value=response):
        propositions = PropositionExtractor().extract_many(["First.", "Second."])
    assert propositions[0].degraded is False
    assert propositions[1].degraded is True


# ----------------------------------------------------------------------
# Evidence extraction
# ----------------------------------------------------------------------
def _scripted(stance: str, dimensions: list[DimensionComparison], confidence: float = 0.5) -> ScriptedEngine:
    return ScriptedEngine(
        {
            "stance": stance,
            "dimensions": dimensions,
            "confidence": confidence,
        }
    )


def test_extraction_never_marks_an_unrelated_document_as_support() -> None:
    """A document that only shares the topic is not supporting evidence."""
    engine = _scripted("context", [_comparison("subject", "absent")], 0.3)
    evidence = EvidenceExtractor(engine).extract(
        FakeSubclaim(text="The council cut the fee in 2024."),
        FakeDocument(text="A report about an unrelated sporting event, with quotes and descriptions."),
    )
    assert evidence.stance.value != "supports"
    assert evidence.assessment_status.value == "assessed"


def test_extraction_records_the_dimension_analysis_on_the_evidence_row() -> None:
    engine = _scripted("contradicts", [_comparison("object", "conflict", "a different object")], 0.7)
    evidence = EvidenceExtractor(engine).extract(
        FakeSubclaim(text="A landed on B in 2023."), FakeDocument(text="A landed on C in 2023.")
    )
    assert evidence.stance.value == "contradicts"
    assert evidence.extra_metadata["entailment"]["dimension_conflicts"]["object"] == "a different object"
    assert "proposition" in evidence.extra_metadata


def test_extraction_falls_back_to_the_title_when_a_document_has_no_body() -> None:
    engine = _scripted("context", [], 0.3)
    evidence = EvidenceExtractor(engine).extract(
        FakeSubclaim(text="A proposition."), FakeDocument(text="", title="A headline about the proposition.")
    )
    assert evidence.raw_excerpt == "A headline about the proposition."


# ----------------------------------------------------------------------
# Verification guard rails
# ----------------------------------------------------------------------
def _evidence(stance: str, evidence_id: int, group: int | None = None) -> Mock:
    item = Mock()
    item.stance = stance
    item.id = evidence_id
    item.subclaim_id = 1
    item.summary = f"{stance} item {evidence_id}"
    item.url = f"https://example.com/{evidence_id}"
    item._independence_group = group
    return item


def _independence(groups: int, group_for_evidence: dict | None = None) -> dict:
    return {
        "independent_groups": groups,
        "group_for_evidence": group_for_evidence or {},
    }


def test_supported_verdict_is_refused_when_no_evidence_supports_the_claim() -> None:
    """An unsupported model conclusion must not become a verified conclusion."""
    agent = VerificationAgent(llm=Mock())
    agent.llm.generate_structured = Mock(side_effect=LLMUnavailableError("down"))

    result = agent.verify(
        FakeSubclaim(text="A proposition."),
        [_evidence("context", 1), _evidence("neutral", 2)],
        independence_summary=_independence(2),
    )
    assert result["verdict"] != "supported"
    assert "no_supporting_evidence" in result["applied_rules"] or result["verdict"] == "insufficient_evidence"


def test_contradicting_evidence_blocks_a_supported_verdict() -> None:
    agent = VerificationAgent(llm=Mock())
    agent.llm.generate_structured = Mock(
        return_value=Mock(
            model_dump=lambda: {"verdict": "supported", "confidence": 0.9, "rationale": "Looks fine."}
        )
    )
    result = agent.verify(
        FakeSubclaim(text="A proposition."),
        [_evidence("supports", 1), _evidence("contradicts", 2)],
        independence_summary=_independence(2, {"1": 1, "2": 2}),
    )
    assert result["verdict"] == "partially_supported"
    assert "contradicting_evidence_present" in result["applied_rules"]


def test_single_independent_source_cannot_be_reported_as_fully_supported() -> None:
    agent = VerificationAgent(llm=Mock())
    agent.llm.generate_structured = Mock(
        return_value=Mock(
            model_dump=lambda: {"verdict": "supported", "confidence": 0.9, "rationale": "Looks fine."}
        )
    )
    result = agent.verify(
        FakeSubclaim(text="A proposition."),
        [_evidence("supports", 1), _evidence("supports", 2)],
        independence_summary=_independence(1, {"1": 1, "2": 1}),
    )
    assert result["verdict"] == "partially_supported"
    assert "single_independent_source" in result["applied_rules"]


def test_article_count_alone_cannot_produce_high_confidence() -> None:
    """Ten copies of one story must not outrank three independent sources."""
    agent = VerificationAgent(llm=Mock())
    agent.llm.generate_structured = Mock(
        return_value=Mock(
            model_dump=lambda: {"verdict": "supported", "confidence": 0.95, "rationale": "Many articles."}
        )
    )

    many_from_one_group = agent.verify(
        FakeSubclaim(text="A proposition."),
        [_evidence("supports", index, 1) for index in range(1, 11)],
        independence_summary=_independence(1, {str(index): 1 for index in range(1, 11)}),
    )
    few_from_many_groups = agent.verify(
        FakeSubclaim(text="A proposition."),
        [_evidence("supports", 21, 1), _evidence("supports", 22, 2), _evidence("supports", 23, 3)],
        independence_summary=_independence(3, {"21": 1, "22": 2, "23": 3}),
    )

    assert many_from_one_group["confidence"] < few_from_many_groups["confidence"]
    assert many_from_one_group["confidence"] <= 0.62


def test_confidence_is_capped_by_the_number_of_independent_groups() -> None:
    agent = VerificationAgent(llm=Mock())
    agent.llm.generate_structured = Mock(
        return_value=Mock(
            model_dump=lambda: {"verdict": "supported", "confidence": 0.99, "rationale": "Very sure."}
        )
    )
    result = agent.verify(
        FakeSubclaim(text="A proposition."),
        [_evidence("supports", 1, 1), _evidence("supports", 2, 2)],
        independence_summary=_independence(2, {"1": 1, "2": 2}),
    )
    assert "confidence_capped_by_independence" in result["applied_rules"]
    assert result["confidence"] <= 0.78


def test_missing_primary_evidence_does_not_force_unverifiable() -> None:
    agent = VerificationAgent(llm=Mock())
    agent.llm.generate_structured = Mock(
        return_value=Mock(
            model_dump=lambda: {"verdict": "supported", "confidence": 0.7, "rationale": "Supported."}
        )
    )
    result = agent.verify(
        FakeSubclaim(text="A proposition."),
        [_evidence("supports", 1, 1), _evidence("supports", 2, 2)],
        primary_status="NOT_CONFIGURED",
        independence_summary=_independence(2, {"1": 1, "2": 2}),
    )
    assert result["verdict"] != "unverifiable"
    assert result["primary_evidence_status"] == "NOT_CONFIGURED"


def test_search_failed_primary_evidence_reduces_confidence() -> None:
    agent = VerificationAgent(llm=Mock())
    agent.llm.generate_structured = Mock(
        return_value=Mock(
            model_dump=lambda: {"verdict": "supported", "confidence": 0.6, "rationale": "Supported."}
        )
    )
    ok = agent.verify(
        FakeSubclaim(text="A proposition."),
        [_evidence("supports", 1, 1), _evidence("supports", 2, 2)],
        primary_status="NOT_SEARCHED",
        independence_summary=_independence(2, {"1": 1, "2": 2}),
    )
    failed = agent.verify(
        FakeSubclaim(text="A proposition."),
        [_evidence("supports", 1, 1), _evidence("supports", 2, 2)],
        primary_status="SEARCH_FAILED",
        independence_summary=_independence(2, {"1": 1, "2": 2}),
    )
    assert failed["confidence"] < ok["confidence"]


def test_completeness_can_downgrade_but_never_upgrade() -> None:
    agent = VerificationAgent(llm=Mock())
    agent.llm.generate_structured = Mock(
        return_value=Mock(
            model_dump=lambda: {"verdict": "insufficient_evidence", "confidence": 0.3, "rationale": "Thin."}
        )
    )
    upgraded = agent.verify(
        FakeSubclaim(text="A proposition."),
        [_evidence("context", 1)],
        completeness_result={"completeness_status": "MISLEADING_BY_OMISSION", "missing_context": []},
        independence_summary=_independence(2),
    )
    assert upgraded["verdict"] == "insufficient_evidence"


# ----------------------------------------------------------------------
# Independence
# ----------------------------------------------------------------------
def test_syndicated_copies_collapse_into_one_independent_group(session) -> None:
    from app.models import (
        Claim,
        Document,
        DocumentSourceType,
        Publisher,
        PublisherType,
        SourceRelationship,
        SourceRelationshipType,
    )

    claim = Claim(claim_text="A claim.")
    session.add(claim)
    session.flush()

    original_publisher = Publisher(name="Original Outlet", publisher_type=PublisherType.NEWS.value)
    copy_publisher = Publisher(name="Copy Outlet", publisher_type=PublisherType.NEWS.value)
    original = Document(
        publisher=original_publisher,
        url="https://original.example/story",
        canonical_url="https://original.example/story",
        title="The story",
        source_type=DocumentSourceType.NEWS,
        content_hash="hash-a",
        text_content="The body of the story, published first by the original outlet.",
    )
    republished = Document(
        publisher=copy_publisher,
        url="https://copy.example/story",
        canonical_url="https://copy.example/story",
        title="The story",
        source_type=DocumentSourceType.NEWS,
        content_hash="hash-a",
        text_content="The body of the story, published first by the original outlet.",
    )
    session.add_all([original_publisher, copy_publisher, original, republished])
    session.flush()
    session.add(
        SourceRelationship(
            source_document_id=republished.id,
            target_document_id=original.id,
            relationship_type=SourceRelationshipType.SYNDICATED_FROM,
            confidence=0.9,
        )
    )
    session.flush()

    summary = IndependenceAnalyzer().analyze(session, claim, [original, republished], [])
    assert summary.distinct_publishers == 2
    assert summary.independent_groups == 1
    assert summary.dependency_edges == 1


def test_distinct_publishers_form_distinct_groups(session) -> None:
    from app.models import (
        Claim,
        Document,
        DocumentSourceType,
        Publisher,
        PublisherType,
    )

    claim = Claim(claim_text="A claim.")
    session.add(claim)
    session.flush()

    documents = []
    for index in range(3):
        publisher = Publisher(name=f"Outlet {index}", publisher_type=PublisherType.NEWS.value)
        document = Document(
            publisher=publisher,
            url=f"https://outlet{index}.example/story",
            canonical_url=f"https://outlet{index}.example/story",
            title=f"Story {index}",
            source_type=DocumentSourceType.NEWS,
            content_hash=f"hash-{index}",
            text_content=f"A completely different body of reporting number {index}.",
        )
        session.add_all([publisher, document])
        documents.append(document)
    session.flush()

    summary = IndependenceAnalyzer().analyze(session, claim, documents, [])
    assert summary.independent_groups == 3


# ----------------------------------------------------------------------
# Deduplication
# ----------------------------------------------------------------------
def test_near_duplicate_articles_are_collapsed_and_linked(session) -> None:
    from app.models import Document, DocumentSourceType, Publisher, PublisherType

    publisher = Publisher(name="Wire Service", publisher_type=PublisherType.NEWS.value)
    original = Document(
        publisher=publisher,
        url="https://wire.example/story",
        canonical_url="https://wire.example/story",
        title="Council approves the budget",
        source_type=DocumentSourceType.NEWS,
        text_content="The city council approved the budget on Tuesday evening after a long debate.",
    )
    republished = Document(
        publisher=publisher,
        url="https://otheroutlet.example/story",
        canonical_url="https://otheroutlet.example/story",
        title="Council approves the budget",
        source_type=DocumentSourceType.NEWS,
        text_content="The city council approved the budget on Tuesday evening after a long debate.",
    )
    session.add_all([publisher, original, republished])
    session.flush()

    survivors = DeduplicationService.normalize_and_dedupe(session, [original, republished])
    assert len(survivors) == 1

    from app.models import SourceRelationship, SourceRelationshipType

    relationship = (
        session.query(SourceRelationship)
        .filter(SourceRelationship.relationship_type == SourceRelationshipType.SYNDICATED_FROM)
        .first()
    )
    assert relationship is not None


def test_unrelated_articles_are_not_collapsed(session) -> None:
    from app.models import Document, DocumentSourceType, Publisher, PublisherType

    publisher = Publisher(name="Wire Service", publisher_type=PublisherType.NEWS.value)
    first = Document(
        publisher=publisher,
        url="https://wire.example/a",
        canonical_url="https://wire.example/a",
        title="Council approves the budget",
        source_type=DocumentSourceType.NEWS,
        text_content="The city council approved the budget on Tuesday evening after a long debate.",
    )
    second = Document(
        publisher=publisher,
        url="https://wire.example/b",
        canonical_url="https://wire.example/b",
        title="Heavy rain closes the highway",
        source_type=DocumentSourceType.NEWS,
        text_content="Storms brought flooding to the coastal region, closing a major highway for two days.",
    )
    session.add_all([publisher, first, second])
    session.flush()

    survivors = DeduplicationService.normalize_and_dedupe(session, [first, second])
    assert len(survivors) == 2


def test_tracking_parameters_do_not_create_duplicate_documents(session) -> None:
    from app.models import Document, DocumentSourceType, Publisher, PublisherType

    publisher = Publisher(name="Wire Service", publisher_type=PublisherType.NEWS.value)
    first = Document(
        publisher=publisher,
        url="https://wire.example/story",
        canonical_url="https://wire.example/story",
        title="A story",
        source_type=DocumentSourceType.NEWS,
    )
    second = Document(
        publisher=publisher,
        url="https://wire.example/story?utm_source=newsletter",
        canonical_url="https://wire.example/story?utm_source=newsletter",
        title="A story",
        source_type=DocumentSourceType.NEWS,
    )
    session.add_all([publisher, first, second])
    session.flush()

    survivors = DeduplicationService.normalize_and_dedupe(session, [first, second])
    assert len(survivors) == 1


# ----------------------------------------------------------------------
# Stance helpers
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("supports", "supports"),
        ("SUPPORTS", "supports"),
        (None, "unknown"),
        ("nonsense", "unknown"),
    ],
)
def test_stance_normalisation(raw, expected) -> None:
    assert normalise_stance(raw) == expected
