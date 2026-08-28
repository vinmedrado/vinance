"""create ml features tables

Revision ID: 0006_create_ml_features_tables
Revises: 0005_create_market_fundamentals
Create Date: 2026-06-09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_create_ml_features_tables"
down_revision = "0005_create_market_fundamentals"
branch_labels = None
depends_on = None


ML_FEATURE_TABLES = (
    "fii_ml_features",
    "acoes_ml_features",
    "etf_ml_features",
    "bdr_ml_features",
    "cripto_ml_features",
)


def _create_ml_features_table(table_name: str) -> None:
    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("momentum_30d", sa.Float(), nullable=True),
        sa.Column("momentum_90d", sa.Float(), nullable=True),
        sa.Column("volatilidade_30d", sa.Float(), nullable=True),
        sa.Column("score_final", sa.Float(), nullable=True),
        sa.Column(
            "calculado_em",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("ticker", "date", name=f"uq_{table_name}_ticker_date"),
    )
    op.create_index(f"ix_{table_name}_ticker", table_name, ["ticker"])
    op.create_index(f"ix_{table_name}_date", table_name, ["date"])


def upgrade() -> None:
    for table_name in ML_FEATURE_TABLES:
        _create_ml_features_table(table_name)


def downgrade() -> None:
    for table_name in reversed(ML_FEATURE_TABLES):
        op.drop_index(f"ix_{table_name}_date", table_name=table_name)
        op.drop_index(f"ix_{table_name}_ticker", table_name=table_name)
        op.drop_table(table_name)
