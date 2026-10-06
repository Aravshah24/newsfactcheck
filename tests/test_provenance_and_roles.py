"""Provenance, evidence role and role-weighted confidence.

The property under test throughout: how much evidence exists is never the same
question as how good that evidence is, and the system must never confuse them.
"""

from __future__ import annotations

from unittest.mock import Mock

from app.agents.verification import VerificationAgent
from app.models import VerificationVerdict
from app.services.evidence_role import (
    EvidenceRole,
    classify_role,
    has_weight,
    weight_for,
)
from app.services.provenance import NON_SOLE_SUPPORT_CLASSES, ProvenanceClass, classify


# ----------------------------------------------------------------------
# Provenance classification
# ----------------------------------------------------------------------
def test_official_statistics_and_court_records_are_authoritative() -> None:
    statistics = classify(url="https://www.bls.gov/news.release/empsit.toc.htm", source_type="government")
    court = classify(url="https://storage.courtlistener.com/opinion/1/2/3.pdf", source_type="legal")

    assert statistics.provenance_class is ProvenanceClass.OFFICIAL_STATISTIC
    assert court.provenance_class is ProvenanceClass.COURT_RECORD


def test_plain_news_reporting_is_not_treated_as_authoritative() -> None:
    assessment = classify(url="https://www.example-news.com/politics/story", source_type="news")

    assert assessment.provenance_class is ProvenanceClass.NEWS_REPORTING


def test_opinion_columns_are_classified_as_opinion_not_news() -> None:
    assessment = classify(
        url="https://www.example-news.com/politics/analysis",
        source_type="news",
        title="Opinion: why this policy is a disaster",
    )

    assert assessment.provenance_class is ProvenanceClass.OPINION


def test_an_ordinary_retrieved_article_is_classified_as_reporting() -> None:
    """A retrieved result that declares itself news must not fall through to UNKNOWN."""
    assessment = classify(url="https://www.example-news.com/politics/story", source_type="news")

    assert assessment.provenance_class is ProvenanceClass.NEWS_REPORTING


def test_an_unrecognised_source_classifies_as_unknown_rather_than_defaulting_to_trust() -> None:
    assessment = classify(url="", source_type="", publisher=None, title=None)

    assert assessment.provenance_class is ProvenanceClass.UNKNOWN
    assert assessment.provenance_class in NON_SOLE_SUPPORT_CLASSES


# ----------------------------------------------------------------------
# Role classification
# ----------------------------------------------------------------------
def test_republication_is_zero_weight_whatever_it_says() -> None:
    """A wire copy of an authoritative record is still only a republication."""
    derived = classify_role(stance="supports", provenance=ProvenanceClass.OFFICIAL_STATISTIC, is_derived=True)

    assert derived.role is EvidenceRole.DERIVED_REPUBLICATION
    assert weight_for(derived.role) == 0.0


def test_authoritative_support_outranks_a_plain_article() -> None:
    official = classify_role(stance="supports", provenance=ProvenanceClass.COURT_RECORD)
    article = classify_role(stance="supports", provenance=ProvenanceClass.NEWS_REPORTING)

    assert weight_for(official.role) > weight_for(article.role)


def test_opinion_can_never_be_probative_on_its_own() -> None:
    assignment = classify_role(stance="supports", provenance=ProvenanceClass.OPINION)

    assert weight_for(assignment.role) == 0.0
    assert not has_weight(assignment.role)


def test_a_topically_related_document_is_not_evidence_against_or_for() -> None:
    assignment = classify_role(stance="context", provenance=ProvenanceClass.NEWS_REPORTING)

    assert assignment.role is EvidenceRole.TOPICALLY_RELATED
    assert weight_for(assignment.role) == 0.0


# ----------------------------------------------------------------------
# Role-weighted confidence
# ----------------------------------------------------------------------
def _subclaim() -> Mock:
    item = Mock()
    item.text = "A proposition."
    item.id = 1
    return item


def _item(stance: str, evidence_id: int, role: str) -> Mock:
    item = Mock()
    item.stance = stance
    item.id = evidence_id
    item.subclaim_id = 1
    item.summary = f"{stance} via {role}"
    item.url = f"https://example.com/{evidence_id}"
    item.role = role
    return item


def _proposing(verdict: str, confidence: float) -> VerificationAgent:
    agent = VerificationAgent(llm=Mock())
    agent.llm.generate_structured = Mock(
        return_value=Mock(model_dump=lambda: {"verdict": verdict, "confidence": confidence, "rationale": "Model view."})
    )
    return agent


def test_ten_republications_cannot_outrank_one_official_record() -> None:
    """The central property: quantity of copies is not corroboration."""
    agent = _proposing("supported", 0.99)

    result = agent.verify(
        _subclaim(),
        [_item("supports", index, EvidenceRole.DERIVED_REPUBLICATION.value) for index in range(1, 11)],
        independence_summary={"independent_groups": 10, "group_for_evidence": {str(i): i for i in range(1, 11)}},
    )

    assert result["verdict"] != VerificationVerdict.SUPPORTED.value
    assert result["confidence"] <= 0.35
    assert "sole_secondary_support" in result["applied_rules"]


def test_ten_opinion_articles_do_not_outrank_one_official_record() -> None:
    agent = _proposing("supported", 0.99)

    result = agent.verify(
        _subclaim(),
        [_item("supports", index, EvidenceRole.WEAK_CORROBORATION.value) for index in range(1, 11)],
        independence_summary={"independent_groups": 10, "group_for_evidence": {str(i): i for i in range(1, 11)}},
    )

    assert result["verdict"] == VerificationVerdict.INSUFFICIENT_EVIDENCE.value
    assert "sole_secondary_support" in result["applied_rules"]


def test_an_official_record_outranks_article_volume_at_equal_independence() -> None:
    """At equal independence, the record beats the report about it."""
    official = _proposing("supported", 0.99)
    article = _proposing("supported", 0.99)

    official_result = official.verify(
        _subclaim(),
        [_item("supports", 1, EvidenceRole.PRIMARY_CONFIRMATION.value)],
        independence_summary={"independent_groups": 1, "group_for_evidence": {"1": 1}},
    )
    article_result = article.verify(
        _subclaim(),
        [_item("supports", 1, EvidenceRole.INDEPENDENT_CORROBORATION.value)],
        independence_summary={"independent_groups": 1, "group_for_evidence": {"1": 1}},
    )

    assert official_result["role_weighted_support"] > article_result["role_weighted_support"]
    assert official_result["confidence"] > article_result["confidence"]


def test_several_independent_outlets_still_beat_one_record() -> None:
    """Five independent outlets is real evidence, and is not scored as one."""
    agent = _proposing("supported", 0.99)

    result = agent.verify(
        _subclaim(),
        [_item("supports", index, EvidenceRole.INDEPENDENT_CORROBORATION.value) for index in range(1, 6)],
        independence_summary={"independent_groups": 5, "group_for_evidence": {str(i): i for i in range(1, 6)}},
    )

    assert result["role_weighted_support"] == 3.0
    assert result["confidence"] <= 0.90


def test_an_official_record_is_not_dragged_down_by_lack_of_a_second_witness() -> None:
    """A primary record is ground truth, so the independence cap must not apply."""
    agent = _proposing("supported", 0.99)

    result = agent.verify(
        _subclaim(),
        [_item("supports", 1, EvidenceRole.PRIMARY_CONFIRMATION.value)],
        independence_summary={"independent_groups": 1, "group_for_evidence": {"1": 1}},
    )

    assert "confidence_capped_by_independence" not in result["applied_rules"]
    assert result["confidence"] > 0.86


def test_support_restricted_to_weak_roles_is_capped_at_the_role_ceiling() -> None:
    agent = _proposing("partially_supported", 0.9)

    result = agent.verify(
        _subclaim(),
        [_item("supports", 1, EvidenceRole.EXPERT_ASSERTION.value)],
        independence_summary={"independent_groups": 1, "group_for_evidence": {"1": 1}},
    )

    assert result["role_weighted_support"] == 0.8
    assert result["confidence"] <= 0.86


def test_conflicting_official_records_are_reported_as_disputed() -> None:
    """Two authoritative records that disagree cannot yield a positive verdict."""
    agent = _proposing("supported", 0.95)

    result = agent.verify(
        _subclaim(),
        [
            _item("supports", 1, EvidenceRole.PRIMARY_CONFIRMATION.value),
            _item("contradicts", 2, EvidenceRole.CONTRADICTORY_OFFICIAL.value),
        ],
        independence_summary={"independent_groups": 2, "group_for_evidence": {"1": 1, "2": 2}},
    )

    assert result["verdict"] == VerificationVerdict.DISPUTED.value
    assert "conflicting_primary_records" in result["applied_rules"]


def test_evidence_within_one_group_counts_once() -> None:
    """Five documents in one group are one witness, not five."""
    agent = _proposing("supported", 0.99)

    result = agent.verify(
        _subclaim(),
        [_item("supports", index, EvidenceRole.PRIMARY_CONFIRMATION.value) for index in range(1, 6)],
        independence_summary={"independent_groups": 1, "group_for_evidence": {str(i): 1 for i in range(1, 6)}},
    )

    assert result["role_weighted_support"] == 1.0


def test_an_unclassified_source_carries_no_weight() -> None:
    agent = _proposing("supported", 0.99)

    result = agent.verify(
        _subclaim(),
        [_item("supports", 1, EvidenceRole.UNKNOWN.value)],
        independence_summary={"independent_groups": 1, "group_for_evidence": {"1": 1}},
    )

    assert result["role_weighted_support"] == 0.0
    assert "sole_secondary_support" in result["applied_rules"]
