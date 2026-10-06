"""Record witness provenance on documents and evidence roles on evidence items

Revision ID: 20261001_000005
Revises: 20260930_000004
Create Date: 2026-10-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20261001_000005"
down_revision = "20260930_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Provenance says what kind of witness a document is, not how trustworthy
    # it is, so the rule that produced the class is stored for inspection.
    op.add_column("documents", sa.Column("provenance_class", sa.String(length=32), nullable=True))
    op.add_column("documents", sa.Column("provenance_rule", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("provenance_basis", sa.String(length=255), nullable=True))
    op.create_index("ix_documents_provenance_class", "documents", ["provenance_class"])

    # Role weight is the contribution cap that keeps republications, opinion and
    # tertiary sources from adding support at any quantity.
    op.add_column("evidence_items", sa.Column("role", sa.String(length=32), nullable=True))
    op.add_column("evidence_items", sa.Column("role_reason", sa.String(length=255), nullable=True))
    op.add_column("evidence_items", sa.Column("role_weight", sa.Float(), nullable=True))
    op.create_index("ix_evidence_items_role", "evidence_items", ["role"])


def downgrade() -> None:
    op.drop_index("ix_evidence_items_role", table_name="evidence_items")
    op.drop_column("evidence_items", "role_weight")
    op.drop_column("evidence_items", "role_reason")
    op.drop_column("evidence_items", "role")
    op.drop_index("ix_documents_provenance_class", table_name="documents")
    op.drop_column("documents", "provenance_basis")
    op.drop_column("documents", "provenance_rule")
    op.drop_column("documents", "provenance_class")