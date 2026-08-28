"""create market data base

Revision ID: 0004_create_market_data_base
Revises: 0003_create_asset_catalog
Create Date: 2026-06-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_create_market_data_base"
down_revision = "0003_create_asset_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_prices",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(18, 6), nullable=True),
        sa.Column("high", sa.Numeric(18, 6), nullable=True),
        sa.Column("low", sa.Numeric(18, 6), nullable=True),
        sa.Column("close", sa.Numeric(18, 6), nullable=False),
        sa.Column("volume", sa.Numeric(24, 6), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("ticker", "market", "date", "source", name="uq_asset_prices_ticker_market_date_source"),
    )
    op.create_index("ix_asset_prices_ticker", "asset_prices", ["ticker"])
    op.create_index("ix_asset_prices_market", "asset_prices", ["market"])
    op.create_index("ix_asset_prices_date", "asset_prices", ["date"])

    op.create_table(
        "macro_indicators",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(18, 6), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code", "date", "source", name="uq_macro_indicators_code_date_source"),
    )
    op.create_index("ix_macro_indicators_code", "macro_indicators", ["code"])
    op.create_index("ix_macro_indicators_date", "macro_indicators", ["date"])

    op.create_table(
        "renda_fixa_produtos",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("emissor", sa.String(length=160), nullable=True),
        sa.Column("tipo", sa.String(length=80), nullable=False),
        sa.Column("indexador", sa.String(length=80), nullable=True),
        sa.Column("taxa_juros", sa.Numeric(18, 6), nullable=True),
        sa.Column("taxa_total_equiv", sa.Numeric(18, 6), nullable=True),
        sa.Column("vencimento", sa.Date(), nullable=True),
        sa.Column("liquidez_dias", sa.Integer(), nullable=True),
        sa.Column("investimento_minimo", sa.Numeric(18, 2), nullable=True),
        sa.Column("garantia_fgc", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("codigo_tesouro", sa.String(length=80), nullable=True),
        sa.Column("selic_vigente", sa.Numeric(18, 6), nullable=True),
        sa.Column("ipca_12m", sa.Numeric(18, 6), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("coletado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("nome", "emissor", "tipo", "vencimento", "source", name="uq_renda_fixa_produtos_identity"),
    )
    op.create_index("ix_renda_fixa_produtos_tipo", "renda_fixa_produtos", ["tipo"])
    op.create_index("ix_renda_fixa_produtos_indexador", "renda_fixa_produtos", ["indexador"])
    op.create_index("ix_renda_fixa_produtos_is_active", "renda_fixa_produtos", ["is_active"])
    op.create_index("ix_renda_fixa_produtos_coletado_em", "renda_fixa_produtos", ["coletado_em"])


def downgrade() -> None:
    op.drop_index("ix_renda_fixa_produtos_coletado_em", table_name="renda_fixa_produtos")
    op.drop_index("ix_renda_fixa_produtos_is_active", table_name="renda_fixa_produtos")
    op.drop_index("ix_renda_fixa_produtos_indexador", table_name="renda_fixa_produtos")
    op.drop_index("ix_renda_fixa_produtos_tipo", table_name="renda_fixa_produtos")
    op.drop_table("renda_fixa_produtos")
    op.drop_index("ix_macro_indicators_date", table_name="macro_indicators")
    op.drop_index("ix_macro_indicators_code", table_name="macro_indicators")
    op.drop_table("macro_indicators")
    op.drop_index("ix_asset_prices_date", table_name="asset_prices")
    op.drop_index("ix_asset_prices_market", table_name="asset_prices")
    op.drop_index("ix_asset_prices_ticker", table_name="asset_prices")
    op.drop_table("asset_prices")
