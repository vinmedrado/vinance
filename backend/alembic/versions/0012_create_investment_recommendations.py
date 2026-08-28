"""create investment recommendations table

Revision ID: 0012_investment_recommendations
Revises: 0011_asset_scores
Create Date: 2026-06-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0012_investment_recommendations"
down_revision = "0011_asset_scores"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investment_recommendations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("budget", sa.Numeric(18, 2), nullable=False),
        sa.Column("market", sa.String(length=24), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("score_total", sa.Numeric(8, 4), nullable=False),
        sa.Column("price", sa.Numeric(18, 6), nullable=False),
        sa.Column("quantity_possible", sa.Integer(), nullable=False),
        sa.Column("invested_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("recommendation_rank", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_investment_recommendations_budget_market_generated_at",
        "investment_recommendations",
        ["budget", "market", "generated_at"],
    )
    op.create_index(
        "ix_investment_recommendations_market_rank",
        "investment_recommendations",
        ["market", "recommendation_rank"],
    )


def downgrade() -> None:
    op.drop_index("ix_investment_recommendations_market_rank", table_name="investment_recommendations")
    op.drop_index("ix_investment_recommendations_budget_market_generated_at", table_name="investment_recommendations")
    op.drop_table("investment_recommendations")
