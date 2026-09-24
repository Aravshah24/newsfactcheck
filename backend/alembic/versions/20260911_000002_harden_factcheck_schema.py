"""Harden evidence semantics and document relationship integrity

Revision ID: 20260911_000002
Revises: 20250112_000001
Create Date: 2026-09-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260911_000002"
down_revision = "20250112_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("normalized_url", sa.String(length=2048), nullable=True))
    op.create_index("ix_documents_normalized_url", "documents", ["normalized_url"], unique=False)

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE documents ADD CONSTRAINT ck_documents_source_type CHECK (source_type IN ('primary', 'authoritative', 'news', 'press_release', 'blog', 'social', 'official', 'other'))"
        )

    op.add_column(
        "evidence_items",
        sa.Column("stance", sa.String(length=32), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "evidence_items",
        sa.Column("assessment_status", sa.String(length=32), nullable=False, server_default="unassessed"),
    )

    op.execute(
        """
        UPDATE evidence_items
        SET stance = CASE
            WHEN support_status = 'supports' THEN 'supports'
            WHEN support_status = 'contradicts' THEN 'contradicts'
            WHEN support_status = 'mixed' THEN 'neutral'
            WHEN support_status = 'no_evidence' THEN 'unknown'
            ELSE 'unknown'
        END,
        assessment_status = 'unassessed'
        WHERE support_status IS NOT NULL
        """
    )

    op.drop_column("evidence_items", "support_status")

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE evidence_items ADD CONSTRAINT ck_evidence_items_category CHECK (category IN ('raw', 'agent_interpretation', 'verified_conclusion'))"
        )
        op.execute(
            "ALTER TABLE evidence_items ADD CONSTRAINT ck_evidence_items_stance CHECK (stance IN ('supports', 'contradicts', 'context', 'neutral', 'unknown'))"
        )
        op.execute(
            "ALTER TABLE evidence_items ADD CONSTRAINT ck_evidence_items_assessment_status CHECK (assessment_status IN ('unassessed', 'assessed', 'verified', 'rejected'))"
        )

    op.create_unique_constraint(
        "uq_source_relationships_pair_type",
        "source_relationships",
        ["source_document_id", "target_document_id", "relationship_type"],
    )
    op.create_index(
        "ix_source_relationships_source_target",
        "source_relationships",
        ["source_document_id", "target_document_id"],
        unique=False,
    )
    op.create_index(
        "ix_source_relationships_target_source",
        "source_relationships",
        ["target_document_id", "source_document_id"],
        unique=False,
    )
    op.create_index(
        "ix_source_relationships_relationship_type",
        "source_relationships",
        ["relationship_type"],
        unique=False,
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE source_relationships ADD CONSTRAINT ck_source_relationships_type CHECK (relationship_type IN ('syndicated_from', 'copied_from', 'quotes', 'cites', 'translates', 'updates', 'related', 'unknown'))"
        )
        op.execute(
            "ALTER TABLE source_relationships ADD CONSTRAINT ck_source_relationships_no_self_loop CHECK (source_document_id <> target_document_id)"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE source_relationships DROP CONSTRAINT IF EXISTS ck_source_relationships_no_self_loop")
        op.execute("ALTER TABLE source_relationships DROP CONSTRAINT IF EXISTS ck_source_relationships_type")
        op.execute("ALTER TABLE evidence_items DROP CONSTRAINT IF EXISTS ck_evidence_items_assessment_status")
        op.execute("ALTER TABLE evidence_items DROP CONSTRAINT IF EXISTS ck_evidence_items_stance")
        op.execute("ALTER TABLE evidence_items DROP CONSTRAINT IF EXISTS ck_evidence_items_category")
        op.execute("ALTER TABLE documents DROP CONSTRAINT IF EXISTS ck_documents_source_type")

    op.drop_index(op.f("ix_source_relationships_relationship_type"), table_name="source_relationships")
    op.drop_index(op.f("ix_source_relationships_target_source"), table_name="source_relationships")
    op.drop_index(op.f("ix_source_relationships_source_target"), table_name="source_relationships")
    op.drop_constraint("uq_source_relationships_pair_type", "source_relationships", type_="unique")

    op.add_column(
        "evidence_items",
        sa.Column("support_status", sa.String(length=32), nullable=True, server_default="unknown"),
    )
    op.execute(
        """
        UPDATE evidence_items
        SET support_status = CASE
            WHEN stance = 'supports' THEN 'supports'
            WHEN stance = 'contradicts' THEN 'contradicts'
            WHEN stance = 'neutral' THEN 'mixed'
            WHEN stance = 'unknown' THEN 'no_evidence'
            ELSE 'unknown'
        END
        """
    )
    op.drop_column("evidence_items", "assessment_status")
    op.drop_column("evidence_items", "stance")

    op.drop_index(op.f("ix_documents_normalized_url"), table_name="documents")
    op.drop_column("documents", "normalized_url")
