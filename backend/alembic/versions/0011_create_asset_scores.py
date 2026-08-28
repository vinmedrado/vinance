"""create asset scores table

Revision ID: 0011_asset_scores
Revises: 0010_crypto_intraday
Create Date: 2026-06-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0011_asset_scores"
down_revision = "0010_crypto_intraday"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=24), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("score_total", sa.Numeric(8, 4), nullable=False),
        sa.Column("score_value", sa.Numeric(8, 4), nullable=True),
        sa.Column("score_quality", sa.Numeric(8, 4), nullable=True),
        sa.Column("score_dividend", sa.Numeric(8, 4), nullable=True),
        sa.Column("score_liquidity", sa.Numeric(8, 4), nullable=True),
        sa.Column("score_risk", sa.Numeric(8, 4), nullable=True),
        sa.Column("price", sa.Numeric(18, 6), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False, server_default="vinance_score_v1"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "market", "date", "source", name="uq_asset_scores_ticker_market_date_source"),
    )
    op.create_index("ix_asset_scores_market_date_score", "asset_scores", ["market", "date", "score_total"])
    op.create_index("ix_asset_scores_ticker_market", "asset_scores", ["ticker", "market"])


def downgrade() -> None:
    op.drop_index("ix_asset_scores_ticker_market", table_name="asset_scores")
    op.drop_index("ix_asset_scores_market_date_score", table_name="asset_scores")
    op.drop_table("asset_scores")
