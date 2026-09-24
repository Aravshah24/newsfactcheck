"""Create core fact-checking schema

Revision ID: 20250112_000001
Revises: 
Create Date: 2025-01-12 00:00:01.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20250112_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "claims",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("normalized_claim", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(op.f("ix_claims_id"), "claims", ["id"], unique=False)

    op.create_table(
        "subclaims",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("subclaim_type", sa.String(length=30), nullable=False, server_default="other"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(op.f("ix_subclaims_id"), "subclaims", ["id"], unique=False)
    op.create_index(op.f("ix_subclaims_claim_id"), "subclaims", ["claim_id"], unique=False)

    op.create_table(
        "publishers",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("publisher_type", sa.String(length=30), nullable=False, server_default="news"),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(op.f("ix_publishers_id"), "publishers", ["id"], unique=False)
    op.create_index(op.f("ix_publishers_name"), "publishers", ["name"], unique=False)
    op.create_index(op.f("ix_publishers_domain"), "publishers", ["domain"], unique=False)

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("publisher_id", sa.Integer(), sa.ForeignKey("publishers.id"), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("canonical_url", sa.String(length=2048), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language", sa.String(length=20), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=30), nullable=False, server_default="news"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(op.f("ix_documents_id"), "documents", ["id"], unique=False)
    op.create_index(op.f("ix_documents_url"), "documents", ["url"], unique=False)
    op.create_index(op.f("ix_documents_canonical_url"), "documents", ["canonical_url"], unique=False)
    op.create_index(op.f("ix_documents_content_hash"), "documents", ["content_hash"], unique=False)
    op.create_unique_constraint("uq_documents_url", "documents", ["url"])
    op.create_unique_constraint("uq_documents_canonical_url", "documents", ["canonical_url"])

    op.create_table(
        "evidence_items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("subclaim_id", sa.Integer(), sa.ForeignKey("subclaims.id"), nullable=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False, server_default="raw"),
        sa.Column("support_status", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("raw_excerpt", sa.Text(), nullable=True),
        sa.Column("retrieval_channel", sa.String(length=128), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(op.f("ix_evidence_items_id"), "evidence_items", ["id"], unique=False)
    op.create_index(op.f("ix_evidence_items_claim_id"), "evidence_items", ["claim_id"], unique=False)
    op.create_index(op.f("ix_evidence_items_subclaim_id"), "evidence_items", ["subclaim_id"], unique=False)
    op.create_index(op.f("ix_evidence_items_document_id"), "evidence_items", ["document_id"], unique=False)

    op.create_table(
        "evidence_clusters",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("clustering_method", sa.String(length=128), nullable=True),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(op.f("ix_evidence_clusters_id"), "evidence_clusters", ["id"], unique=False)
    op.create_index(op.f("ix_evidence_clusters_claim_id"), "evidence_clusters", ["claim_id"], unique=False)

    op.create_table(
        "evidence_cluster_members",
        sa.Column("evidence_item_id", sa.Integer(), sa.ForeignKey("evidence_items.id"), primary_key=True, nullable=False),
        sa.Column("evidence_cluster_id", sa.Integer(), sa.ForeignKey("evidence_clusters.id"), primary_key=True, nullable=False),
    )

    op.create_table(
        "source_relationships",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("source_document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("target_document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("relationship_type", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence_justification", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(op.f("ix_source_relationships_id"), "source_relationships", ["id"], unique=False)

    op.create_table(
        "search_runs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("subclaim_id", sa.Integer(), sa.ForeignKey("subclaims.id"), nullable=True),
        sa.Column("retrieval_channel", sa.String(length=32), nullable=False, server_default="other"),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", sa.JSON(), nullable=True),
    )
    op.create_index(op.f("ix_search_runs_id"), "search_runs", ["id"], unique=False)
    op.create_index(op.f("ix_search_runs_claim_id"), "search_runs", ["claim_id"], unique=False)
    op.create_index(op.f("ix_search_runs_subclaim_id"), "search_runs", ["subclaim_id"], unique=False)

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("agent_name", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=255), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("input_reference", sa.Text(), nullable=True),
        sa.Column("output_reference", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
    )
    op.create_index(op.f("ix_agent_runs_id"), "agent_runs", ["id"], unique=False)
    op.create_index(op.f("ix_agent_runs_claim_id"), "agent_runs", ["claim_id"], unique=False)
    op.create_index(op.f("ix_agent_runs_run_id"), "agent_runs", ["run_id"], unique=True)

    op.create_table(
        "verification_results",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("subclaim_id", sa.Integer(), sa.ForeignKey("subclaims.id"), nullable=False),
        sa.Column("verdict", sa.String(length=40), nullable=False, server_default="insufficient_evidence"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("supporting_evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("contradicting_evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("independent_evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(op.f("ix_verification_results_id"), "verification_results", ["id"], unique=False)
    op.create_index(op.f("ix_verification_results_subclaim_id"), "verification_results", ["subclaim_id"], unique=False)

    op.create_table(
        "completeness_results",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("completeness_level", sa.String(length=30), nullable=False, server_default="unknown"),
        sa.Column("missing_aspects", sa.JSON(), nullable=True),
        sa.Column("relevant_context", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(op.f("ix_completeness_results_id"), "completeness_results", ["id"], unique=False)
    op.create_index(op.f("ix_completeness_results_claim_id"), "completeness_results", ["claim_id"], unique=False)

    op.create_table(
        "media_analyses",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("left_coverage", sa.Float(), nullable=True),
        sa.Column("center_coverage", sa.Float(), nullable=True),
        sa.Column("right_coverage", sa.Float(), nullable=True),
        sa.Column("framing_summary", sa.Text(), nullable=True),
        sa.Column("omitted_context", sa.Text(), nullable=True),
        sa.Column("publisher_distribution", sa.JSON(), nullable=True),
        sa.Column("methodology", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(op.f("ix_media_analyses_id"), "media_analyses", ["id"], unique=False)
    op.create_index(op.f("ix_media_analyses_claim_id"), "media_analyses", ["claim_id"], unique=False)

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("verdict_summary", sa.Text(), nullable=True),
        sa.Column("report_text", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("methodology_version", sa.String(length=128), nullable=True),
    )
    op.create_index(op.f("ix_reports_id"), "reports", ["id"], unique=False)
    op.create_index(op.f("ix_reports_claim_id"), "reports", ["claim_id"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("agent_run_id", sa.Integer(), sa.ForeignKey("agent_runs.id"), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index(op.f("ix_audit_events_id"), "audit_events", ["id"], unique=False)
    op.create_index(op.f("ix_audit_events_claim_id"), "audit_events", ["claim_id"], unique=False)
    op.create_index(op.f("ix_audit_events_agent_run_id"), "audit_events", ["agent_run_id"], unique=False)
    op.create_index(op.f("ix_audit_events_event_type"), "audit_events", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("reports")
    op.drop_table("media_analyses")
    op.drop_table("completeness_results")
    op.drop_table("verification_results")
    op.drop_table("agent_runs")
    op.drop_table("search_runs")
    op.drop_table("source_relationships")
    op.drop_table("evidence_cluster_members")
    op.drop_table("evidence_clusters")
    op.drop_table("evidence_items")
    op.drop_table("documents")
    op.drop_table("publishers")
    op.drop_table("subclaims")
    op.drop_table("claims")
