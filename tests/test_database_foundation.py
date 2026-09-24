import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import (
    Claim,
    ClaimStatus,
    Document,
    DocumentSourceType,
    EvidenceAssessmentStatus,
    EvidenceCategory,
    EvidenceCluster,
    EvidenceItem,
    EvidenceStance,
    MediaAnalysis,
    Publisher,
    PublisherType,
    SourceRelationship,
    SourceRelationshipType,
    Subclaim,
    SubclaimType,
    VerificationResult,
    VerificationVerdict,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    with Session(bind=engine) as session:
        yield session


def test_evidence_stance_and_assessment_are_independent(session: Session) -> None:
    claim = Claim(claim_text="The policy changed.", status=ClaimStatus.DRAFT.value)
    subclaim = Subclaim(claim=claim, text="The policy was changed.", subclaim_type=SubclaimType.FACTUAL.value)
    evidence = EvidenceItem(
        claim=claim,
        subclaim=subclaim,
        summary="A timeline shows the policy changed.",
        category=EvidenceCategory.RAW,
        stance=EvidenceStance.SUPPORTS,
        assessment_status=EvidenceAssessmentStatus.ASSESSED,
    )
    session.add_all([claim, subclaim, evidence])
    session.flush()

    assert evidence.stance == EvidenceStance.SUPPORTS
    assert evidence.assessment_status == EvidenceAssessmentStatus.ASSESSED


def test_raw_evidence_can_have_unknown_stance(session: Session) -> None:
    claim = Claim(claim_text="Raw evidence test.")
    subclaim = Subclaim(claim=claim, text="Raw evidence should not imply a stance.", subclaim_type=SubclaimType.FACTUAL.value)
    evidence = EvidenceItem(
        claim=claim,
        subclaim=subclaim,
        summary="A reporter cites a quote without yet assessing it.",
        category=EvidenceCategory.RAW,
        stance=EvidenceStance.UNKNOWN,
        assessment_status=EvidenceAssessmentStatus.UNASSESSED,
    )
    session = session
    session.add_all([claim, subclaim, evidence])
    session.flush()

    assert evidence.category == EvidenceCategory.RAW
    assert evidence.stance == EvidenceStance.UNKNOWN
    assert evidence.assessment_status == EvidenceAssessmentStatus.UNASSESSED


def test_evidence_can_support_subclaim_without_being_verified(session: Session) -> None:
    claim = Claim(claim_text="Support without verification.")
    subclaim = Subclaim(claim=claim, text="The event occurred.", subclaim_type=SubclaimType.FACTUAL.value)
    evidence = EvidenceItem(
        claim=claim,
        subclaim=subclaim,
        summary="Supportive quote.",
        category=EvidenceCategory.RAW,
        stance=EvidenceStance.SUPPORTS,
        assessment_status=EvidenceAssessmentStatus.ASSESSED,
    )
    session.add_all([claim, subclaim, evidence])
    session.flush()

    assert evidence.stance == EvidenceStance.SUPPORTS
    assert evidence.assessment_status == EvidenceAssessmentStatus.ASSESSED
    assert evidence.assessment_status != EvidenceAssessmentStatus.VERIFIED


def test_duplicate_source_relationship_edges_are_rejected(session: Session) -> None:
    publisher = Publisher(name="Example News", publisher_type=PublisherType.NEWS.value)
    source = Document(
        publisher=publisher,
        url="https://example.com/a",
        canonical_url="https://example.com/a",
        title="A",
        source_type=DocumentSourceType.NEWS,
        content_hash="hash-1",
    )
    target = Document(
        publisher=publisher,
        url="https://example.com/b",
        canonical_url="https://example.com/b",
        title="B",
        source_type=DocumentSourceType.NEWS,
        content_hash="hash-2",
    )
    session.add_all([publisher, source, target])
    session.flush()

    session.add(
        SourceRelationship(
            source_document=source,
            target_document=target,
            relationship_type=SourceRelationshipType.CITES,
            confidence=0.92,
        )
    )
    session.flush()

    dup = SourceRelationship(
        source_document=source,
        target_document=target,
        relationship_type=SourceRelationshipType.CITES,
        confidence=0.95,
    )
    session.add(dup)
    with pytest.raises(IntegrityError):
        session.flush()


def test_self_document_relationships_are_rejected(session: Session) -> None:
    publisher = Publisher(name="Example News", publisher_type=PublisherType.NEWS.value)
    doc = Document(
        publisher=publisher,
        url="https://example.com/self",
        canonical_url="https://example.com/self",
        title="Self",
        source_type=DocumentSourceType.NEWS,
        content_hash="hash-self",
    )
    session.add_all([publisher, doc])
    session.flush()

    session.add(
        SourceRelationship(
            source_document=doc,
            target_document=doc,
            relationship_type=SourceRelationshipType.RELATED,
            confidence=1.0,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_multiple_documents_may_share_content_hash(session: Session) -> None:
    publisher = Publisher(name="Example News", publisher_type=PublisherType.NEWS.value)
    doc_a = Document(
        publisher=publisher,
        url="https://example.com/a-shared",
        canonical_url="https://example.com/a-shared",
        title="A",
        source_type=DocumentSourceType.NEWS,
        content_hash="shared-hash",
    )
    doc_b = Document(
        publisher=publisher,
        url="https://example.com/b-shared",
        canonical_url="https://example.com/b-shared",
        title="B",
        source_type=DocumentSourceType.NEWS,
        content_hash="shared-hash",
    )
    session.add_all([publisher, doc_a, doc_b])
    session.flush()

    assert session.query(Document).filter_by(content_hash="shared-hash").count() == 2


def test_multiple_evidence_items_can_share_one_cluster_and_one_item_can_belong_to_multiple_clusters(session: Session) -> None:
    claim = Claim(claim_text="Evidence clustering.")
    subclaim = Subclaim(claim=claim, text="The event happened.", subclaim_type=SubclaimType.FACTUAL.value)
    cluster_a = EvidenceCluster(claim=claim, label="cluster-a")
    cluster_b = EvidenceCluster(claim=claim, label="cluster-b")
    evidence_a = EvidenceItem(
        claim=claim,
        subclaim=subclaim,
        summary="Evidence A",
        category=EvidenceCategory.RAW,
        stance=EvidenceStance.SUPPORTS,
        assessment_status=EvidenceAssessmentStatus.ASSESSED,
    )
    evidence_b = EvidenceItem(
        claim=claim,
        subclaim=subclaim,
        summary="Evidence B",
        category=EvidenceCategory.RAW,
        stance=EvidenceStance.SUPPORTS,
        assessment_status=EvidenceAssessmentStatus.ASSESSED,
    )
    cluster_a.evidence_items = [evidence_a, evidence_b]
    cluster_b.evidence_items = [evidence_a]
    session.add_all([claim, subclaim, cluster_a, cluster_b, evidence_a, evidence_b])
    session.flush()

    assert len(cluster_a.evidence_items) == 2
    assert len(cluster_b.evidence_items) == 1
    assert evidence_a in cluster_a.evidence_items
    assert evidence_a in cluster_b.evidence_items


def test_document_source_types_support_primary_authoritative_news_social_other(session: Session) -> None:
    publisher = Publisher(name="Source Registry", publisher_type=PublisherType.GOVERNMENT.value)
    for source_type in [
        DocumentSourceType.PRIMARY,
        DocumentSourceType.AUTHORITATIVE,
        DocumentSourceType.NEWS,
        DocumentSourceType.SOCIAL,
        DocumentSourceType.OTHER,
    ]:
        doc = Document(
            publisher=publisher,
            url=f"https://example.com/{source_type.value}",
            canonical_url=f"https://example.com/{source_type.value}",
            title=source_type.value,
            source_type=source_type,
            content_hash=f"hash-{source_type.value}",
        )
        session.add(doc)
    session.flush()

    stored = session.execute(select(Document.source_type)).scalars().all()
    assert {item.value for item in stored} == {
        DocumentSourceType.PRIMARY.value,
        DocumentSourceType.AUTHORITATIVE.value,
        DocumentSourceType.NEWS.value,
        DocumentSourceType.SOCIAL.value,
        DocumentSourceType.OTHER.value,
    }


def test_claim_without_primary_document_does_not_imply_unverifiable(session: Session) -> None:
    claim = Claim(claim_text="No primary source is not automatically UNVERIFIABLE.")
    subclaim = Subclaim(claim=claim, text="The statement is factual.", subclaim_type=SubclaimType.FACTUAL.value)
    verification = VerificationResult(
        subclaim=subclaim,
        verdict=VerificationVerdict.INSUFFICIENT_EVIDENCE,
        confidence=0.2,
        rationale="No primary document yet, but the claim is still under investigation.",
    )
    session.add_all([claim, subclaim, verification])
    session.flush()

    assert verification.subclaim_id == subclaim.id
    assert verification.verdict == VerificationVerdict.INSUFFICIENT_EVIDENCE


def test_verification_result_belongs_to_subclaim_and_media_analysis_is_separate(session: Session) -> None:
    claim = Claim(claim_text="Verification and media analysis separation.")
    subclaim = Subclaim(claim=claim, text="The city has a population increase.", subclaim_type=SubclaimType.QUANTITATIVE.value)
    verification = VerificationResult(
        subclaim=subclaim,
        verdict=VerificationVerdict.SUPPORTED,
        confidence=0.85,
        rationale="Independent figures align.",
    )
    media = MediaAnalysis(
        claim=claim,
        left_coverage=0.1,
        center_coverage=0.4,
        right_coverage=0.5,
        framing_summary="Coverage was skewed to the right.",
    )
    session.add_all([claim, subclaim, verification, media])
    session.flush()

    assert verification.subclaim_id == subclaim.id
    assert media.claim_id == claim.id
    assert VerificationResult.__tablename__ != MediaAnalysis.__tablename__
    assert verification.__table__.name == "verification_results"
    assert media.__table__.name == "media_analyses"
