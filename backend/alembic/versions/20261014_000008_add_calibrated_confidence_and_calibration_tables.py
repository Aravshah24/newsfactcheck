"""Add calibrated_confidence and calibration tables

Revision ID: 20261014_000008
Revises: 20261010_000007
Create Date: 2026-10-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261014_000008"
down_revision = "20261010_000007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # calibrated_confidence on verification_results
    op.add_column(
        "verification_results",
        sa.Column("calibrated_confidence", sa.Float(), nullable=True),
    )

    # calibrated_confidence on subclaim_conclusions
    op.add_column(
        "subclaim_conclusions",
        sa.Column("calibrated_confidence", sa.Float(), nullable=True),
    )

    # ground_truth_calibration table
    op.create_table(
        "ground_truth_calibration",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("subclaim_text", sa.Text(), nullable=False),
        sa.Column("true_verdict", sa.String(40), nullable=False),
        sa.Column("heuristic_confidence", sa.Float(), nullable=False),
        sa.Column("heuristic_verdict", sa.String(40), nullable=False),
        sa.Column("independent_groups", sa.Integer(), default=0, nullable=False),
        sa.Column("role_weighted_support", sa.Float(), nullable=True),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("annotated_by", sa.String(128), nullable=True),
        sa.Column("annotated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_calibration_verdict_confidence", "ground_truth_calibration", ["true_verdict", "heuristic_confidence"])
    op.create_index("ix_calibration_active", "ground_truth_calibration", ["is_active"])

    # calibration_models table
    op.create_table(
        "calibration_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_type", sa.String(32), nullable=False),
        sa.Column("model_data", sa.LargeBinary(), nullable=False),
        sa.Column("training_samples", sa.Integer(), nullable=False),
        sa.Column("ece_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=False, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_calibration_model_active", "calibration_models", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_calibration_model_active", table_name="calibration_models")
    op.drop_table("calibration_models")
    op.drop_index("ix_calibration_active", table_name="ground_truth_calibration")
    op.drop_index("ix_calibration_verdict_confidence", table_name="ground_truth_calibration")
    op.drop_table("ground_truth_calibration")
    op.drop_column("subclaim_conclusions", "calibrated_confidence")
    op.drop_column("verification_results", "calibrated_confidence")