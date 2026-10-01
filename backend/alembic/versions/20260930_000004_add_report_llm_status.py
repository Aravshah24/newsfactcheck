"""Persist the LLM diagnostics that were in force when a report was produced

Revision ID: 20260930_000004
Revises: 20260930_000003
Create Date: 2026-09-30 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260930_000004"
down_revision = "20260930_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Records which provider and model actually answered, so a stored verdict can
    # be read back together with the LLM state that produced it.
    op.add_column("reports", sa.Column("llm_status", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("reports", "llm_status")
