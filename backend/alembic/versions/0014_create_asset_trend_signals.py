"""create asset trend signals table

Revision ID: 0014_asset_trend_signals
Revises: 0013_recommendation_guardrails
Create Date: 2026-06-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0014_asset_trend_signals"
down_revision = "0013_recommendation_guardrails"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_trend_signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=24), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("price", sa.Numeric(18, 6), nullable=True),
        sa.Column("return_1d", sa.Numeric(18, 6), nullable=True),
        sa.Column("return_7d", sa.Numeric(18, 6), nullable=True),
        sa.Column("return_30d", sa.Numeric(18, 6), nullable=True),
        sa.Column("return_90d", sa.Numeric(18, 6), nullable=True),
        sa.Column("return_180d", sa.Numeric(18, 6), nullable=True),
        sa.Column("return_365d", sa.Numeric(18, 6), nullable=True),
        sa.Column("volatility_30d", sa.Numeric(18, 6), nullable=True),
        sa.Column("momentum_score", sa.Numeric(8, 4), nullable=False),
        sa.Column("trend_label", sa.String(length=32), nullable=False),
        sa.Column("risk_label", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "market", "date", "source", name="uq_asset_trend_signals_ticker_market_date_source"),
    )
    op.create_index("ix_asset_trend_signals_market_trend_date", "asset_trend_signals", ["market", "trend_label", "date"])
    op.create_index("ix_asset_trend_signals_market_risk_date", "asset_trend_signals", ["market", "risk_label", "date"])
    op.create_index("ix_asset_trend_signals_ticker_market", "asset_trend_signals", ["ticker", "market"])


def downgrade() -> None:
    op.drop_index("ix_asset_trend_signals_ticker_market", table_name="asset_trend_signals")
    op.drop_index("ix_asset_trend_signals_market_risk_date", table_name="asset_trend_signals")
    op.drop_index("ix_asset_trend_signals_market_trend_date", table_name="asset_trend_signals")
    op.drop_table("asset_trend_signals")
