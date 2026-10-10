"""Persist the unknown bucket in media-coverage analysis

Revision ID: 20261010_000007
Revises: 20261002_000006
Create Date: 2026-10-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20261010_000007"
down_revision = "20261002_000006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The agent always computed the share of publishers with no lean rating but
    # the record had no column, so the unknown bucket was silently dropped.
    op.add_column("media_analyses", sa.Column("unknown_coverage", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("media_analyses", "unknown_coverage")