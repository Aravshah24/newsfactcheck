"""Persist the role-weighted totals behind each confidence value

Revision ID: 20261002_000006
Revises: 20261001_000005
Create Date: 2026-10-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20261002_000006"
down_revision = "20261001_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The agent computed these but the conclusion record had nowhere to keep
    # them, so the arithmetic behind every confidence was discarded on write.
    op.add_column("subclaim_conclusions", sa.Column("role_weighted_support", sa.Float(), nullable=True))
    op.add_column("subclaim_conclusions", sa.Column("role_weighted_contradiction", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("subclaim_conclusions", "role_weighted_contradiction")
    op.drop_column("subclaim_conclusions", "role_weighted_support")