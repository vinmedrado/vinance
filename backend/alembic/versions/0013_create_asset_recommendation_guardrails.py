"""create asset recommendation guardrails table

Revision ID: 0013_recommendation_guardrails
Revises: 0012_investment_recommendations
Create Date: 2026-06-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0013_recommendation_guardrails"
down_revision = "0012_investment_recommendations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_recommendation_guardrails",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=24), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("risk_level", sa.String(length=24), nullable=False),
        sa.Column("penalty_score", sa.Numeric(8, 4), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "market", "date", "source", name="uq_asset_recommendation_guardrails_ticker_market_date_source"),
    )
    op.create_index(
        "ix_asset_recommendation_guardrails_market_status_date",
        "asset_recommendation_guardrails",
        ["market", "status", "date"],
    )
    op.create_index(
        "ix_asset_recommendation_guardrails_ticker_market",
        "asset_recommendation_guardrails",
        ["ticker", "market"],
    )


def downgrade() -> None:
    op.drop_index("ix_asset_recommendation_guardrails_ticker_market", table_name="asset_recommendation_guardrails")
    op.drop_index("ix_asset_recommendation_guardrails_market_status_date", table_name="asset_recommendation_guardrails")
    op.drop_table("asset_recommendation_guardrails")
