"""create immutable investment decision audit trail

Revision ID: 0015_decision_audits
Revises: 0014_asset_trend_signals
Create Date: 2026-08-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0015_decision_audits"
down_revision = "0014_asset_trend_signals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investment_decision_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("decision_id", sa.String(length=36), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("asset", sa.String(length=32), nullable=True),
        sa.Column("market", sa.String(length=24), nullable=True),
        sa.Column("budget", sa.Numeric(18, 2), nullable=False),
        sa.Column("investor_profile", sa.String(length=32), nullable=True),
        sa.Column("recommendation", sa.String(length=24), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("price", sa.Numeric(18, 6), nullable=True),
        sa.Column("invested_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("remaining_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("risk_level", sa.String(length=24), nullable=True),
        sa.Column("confidence", sa.Numeric(8, 4), nullable=True),
        sa.Column("trend", sa.String(length=32), nullable=True),
        sa.Column("ranking", sa.Integer(), nullable=True),
        sa.Column("recommendation_score", sa.Numeric(8, 4), nullable=True),
        sa.Column("guardrail_status", sa.String(length=24), nullable=True),
        sa.Column("guardrail_reasons", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.JSON(), nullable=False),
        sa.Column("request_parameters", sa.JSON(), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("score_snapshot", sa.JSON(), nullable=False),
        sa.Column("response_snapshot", sa.JSON(), nullable=False),
        sa.Column("snapshot_schema_version", sa.String(length=80), nullable=False),
        sa.Column("rule_version", sa.String(length=80), nullable=False),
        sa.Column("recommendation_engine_version", sa.String(length=80), nullable=False),
        sa.Column("score_version", sa.String(length=80), nullable=True),
        sa.Column("guardrail_version", sa.String(length=80), nullable=True),
        sa.Column("trend_version", sa.String(length=80), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("decision_id", name="uq_investment_decision_audits_decision_id"),
    )
    op.create_index("ix_decision_audits_user_created", "investment_decision_audits", ["user_id", "created_at"])
    op.create_index("ix_decision_audits_user_action", "investment_decision_audits", ["user_id", "recommendation", "created_at"])
    op.create_index("ix_decision_audits_user_risk", "investment_decision_audits", ["user_id", "risk_level", "created_at"])
    op.create_index("ix_decision_audits_user_asset", "investment_decision_audits", ["user_id", "asset", "created_at"])
    op.create_index("ix_decision_audits_correlation", "investment_decision_audits", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_decision_audits_correlation", table_name="investment_decision_audits")
    op.drop_index("ix_decision_audits_user_asset", table_name="investment_decision_audits")
    op.drop_index("ix_decision_audits_user_risk", table_name="investment_decision_audits")
    op.drop_index("ix_decision_audits_user_action", table_name="investment_decision_audits")
    op.drop_index("ix_decision_audits_user_created", table_name="investment_decision_audits")
    op.drop_table("investment_decision_audits")
