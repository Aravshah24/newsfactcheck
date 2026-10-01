"""Add verified conclusions and persist report metadata

Creates ``subclaim_conclusions`` so a verified conclusion is stored separately
from the evidence it rests on, and adds the report-level columns the API reads
back (verdict detail, primary evidence status, independence summary, retrieval
stats, and whether live LLM reasoning was available).

Revision ID: 20260930_000003
Revises: 20260911_000002
Create Date: 2026-09-30 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260930_000003"
down_revision = "20260911_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subclaim_conclusions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("subclaim_id", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(length=40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("independent_source_groups", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("supporting_evidence_ids", sa.JSON(), nullable=True),
        sa.Column("applied_rules", sa.JSON(), nullable=True),
        sa.Column("method", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subclaim_id"], ["subclaims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subclaim_conclusions_claim_id", "subclaim_conclusions", ["claim_id"], unique=False)
    op.create_index("ix_subclaim_conclusions_subclaim_id", "subclaim_conclusions", ["subclaim_id"], unique=False)
    op.create_index("ix_subclaim_conclusions_verdict", "subclaim_conclusions", ["verdict"], unique=False)

    op.add_column("reports", sa.Column("overall_confidence", sa.Float(), nullable=True))
    op.add_column("reports", sa.Column("overall_explanation", sa.Text(), nullable=True))
    op.add_column("reports", sa.Column("primary_evidence_status", sa.String(length=32), nullable=True))
    op.add_column("reports", sa.Column("source_independence", sa.JSON(), nullable=True))
    op.add_column("reports", sa.Column("retrieval_stats", sa.JSON(), nullable=True))
    op.add_column("reports", sa.Column("llm_available", sa.Boolean(), nullable=True))

    # Evidence rows produced before this revision were rule-inferred and were never
    # assessed against a decomposed proposition, so they are marked unverified.
    op.execute("UPDATE evidence_items SET assessment_status = 'unassessed' WHERE assessment_status = 'assessed'")


def downgrade() -> None:
    op.drop_column("reports", "llm_available")
    op.drop_column("reports", "retrieval_stats")
    op.drop_column("reports", "source_independence")
    op.drop_column("reports", "primary_evidence_status")
    op.drop_column("reports", "overall_explanation")
    op.drop_column("reports", "overall_confidence")

    op.drop_index("ix_subclaim_conclusions_verdict", table_name="subclaim_conclusions")
    op.drop_index("ix_subclaim_conclusions_subclaim_id", table_name="subclaim_conclusions")
    op.drop_index("ix_subclaim_conclusions_claim_id", table_name="subclaim_conclusions")
    op.drop_table("subclaim_conclusions")
