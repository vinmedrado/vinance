"""create immutable investment decision performance evaluations

Revision ID: 0016_decision_performance
Revises: 0015_decision_audits
Create Date: 2026-08-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0016_decision_performance"
down_revision = "0015_decision_audits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investment_decision_performance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("decision_id", sa.String(length=36), nullable=False),
        sa.Column("horizon", sa.String(length=8), nullable=False),
        sa.Column("reference_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("reference_price_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_source", sa.String(length=80), nullable=False),
        sa.Column("evaluation_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("evaluation_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluation_price_source", sa.String(length=80), nullable=False),
        sa.Column("absolute_change", sa.Numeric(18, 6), nullable=False),
        sa.Column("return_pct", sa.Numeric(12, 6), nullable=False),
        sa.Column("max_favorable_excursion_pct", sa.Numeric(12, 6), nullable=True),
        sa.Column("max_adverse_excursion_pct", sa.Numeric(12, 6), nullable=True),
        sa.Column("result_status", sa.String(length=24), nullable=False, server_default="EVALUATED"),
        sa.Column("result_classification", sa.String(length=32), nullable=False),
        sa.Column("result_context", sa.JSON(), nullable=False),
        sa.Column("evaluation_policy_version", sa.String(length=80), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["investment_decision_audits.decision_id"],
            name="fk_decision_performance_decision_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "decision_id",
            "horizon",
            name="uq_decision_performance_decision_horizon",
        ),
    )
    op.create_index(
        "ix_decision_performance_horizon_evaluated",
        "investment_decision_performance",
        ["horizon", "evaluated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_decision_performance_horizon_evaluated",
        table_name="investment_decision_performance",
    )
    op.drop_table("investment_decision_performance")
