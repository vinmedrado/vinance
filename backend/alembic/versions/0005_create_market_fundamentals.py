"""create market fundamentals by market

Revision ID: 0005_create_market_fundamentals
Revises: 0004_create_market_data_base
Create Date: 2026-06-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_create_market_fundamentals"
down_revision = "0004_create_market_data_base"
branch_labels = None
depends_on = None


def _common_columns():
    return [
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
    ]


def _source_column():
    return [
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("coletado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "fii_fundamentals",
        *_common_columns(),
        sa.Column("price", sa.Numeric(18, 6), nullable=True),
        sa.Column("patrimonio_liq", sa.Numeric(24, 6), nullable=True),
        sa.Column("vpa", sa.Numeric(18, 6), nullable=True),
        sa.Column("pvp", sa.Numeric(18, 6), nullable=True),
        sa.Column("dy_12m", sa.Numeric(18, 6), nullable=True),
        sa.Column("dy_3m_acumulado", sa.Numeric(18, 6), nullable=True),
        sa.Column("ultimo_rendimento", sa.Numeric(18, 6), nullable=True),
        sa.Column("data_ultimo_rend", sa.Date(), nullable=True),
        sa.Column("volume_medio_diario", sa.Numeric(24, 6), nullable=True),
        sa.Column("liquidez_diaria", sa.Numeric(24, 6), nullable=True),
        sa.Column("tipo", sa.String(length=80), nullable=True),
        sa.Column("segmento", sa.String(length=120), nullable=True),
        sa.Column("num_cotistas", sa.Integer(), nullable=True),
        sa.Column("num_imoveis", sa.Integer(), nullable=True),
        sa.Column("vacancia_fisica", sa.Numeric(18, 6), nullable=True),
        sa.Column("vacancia_financeira", sa.Numeric(18, 6), nullable=True),
        sa.Column("gestora", sa.String(length=160), nullable=True),
        sa.Column("administradora", sa.String(length=160), nullable=True),
        sa.Column("taxa_adm", sa.Numeric(18, 6), nullable=True),
        sa.Column("taxa_performance", sa.Numeric(18, 6), nullable=True),
        *_source_column(),
        sa.UniqueConstraint("ticker", "date", "source", name="uq_fii_fundamentals_ticker_date_source"),
    )
    op.create_index("ix_fii_fundamentals_ticker", "fii_fundamentals", ["ticker"])
    op.create_index("ix_fii_fundamentals_date", "fii_fundamentals", ["date"])
    op.create_index("ix_fii_fundamentals_segmento", "fii_fundamentals", ["segmento"])
    op.create_index("ix_fii_fundamentals_source", "fii_fundamentals", ["source"])

    op.create_table(
        "acoes_fundamentals",
        *_common_columns(),
        sa.Column("price", sa.Numeric(18, 6), nullable=True),
        sa.Column("market_cap", sa.Numeric(24, 6), nullable=True),
        sa.Column("pl", sa.Numeric(18, 6), nullable=True),
        sa.Column("pvp", sa.Numeric(18, 6), nullable=True),
        sa.Column("psr", sa.Numeric(18, 6), nullable=True),
        sa.Column("ev_ebitda", sa.Numeric(18, 6), nullable=True),
        sa.Column("ev_ebit", sa.Numeric(18, 6), nullable=True),
        sa.Column("roe", sa.Numeric(18, 6), nullable=True),
        sa.Column("roa", sa.Numeric(18, 6), nullable=True),
        sa.Column("roic", sa.Numeric(18, 6), nullable=True),
        sa.Column("margem_liquida", sa.Numeric(18, 6), nullable=True),
        sa.Column("margem_ebitda", sa.Numeric(18, 6), nullable=True),
        sa.Column("cagr_receita_5a", sa.Numeric(18, 6), nullable=True),
        sa.Column("cagr_lucro_5a", sa.Numeric(18, 6), nullable=True),
        sa.Column("dy_12m", sa.Numeric(18, 6), nullable=True),
        sa.Column("payout", sa.Numeric(18, 6), nullable=True),
        sa.Column("divida_liq_ebitda", sa.Numeric(18, 6), nullable=True),
        sa.Column("volume_medio_diario", sa.Numeric(24, 6), nullable=True),
        sa.Column("setor", sa.String(length=120), nullable=True),
        sa.Column("subsetor", sa.String(length=120), nullable=True),
        *_source_column(),
        sa.UniqueConstraint("ticker", "date", "source", name="uq_acoes_fundamentals_ticker_date_source"),
    )
    op.create_index("ix_acoes_fundamentals_ticker", "acoes_fundamentals", ["ticker"])
    op.create_index("ix_acoes_fundamentals_date", "acoes_fundamentals", ["date"])
    op.create_index("ix_acoes_fundamentals_setor", "acoes_fundamentals", ["setor"])
    op.create_index("ix_acoes_fundamentals_source", "acoes_fundamentals", ["source"])

    op.create_table(
        "etf_fundamentals",
        *_common_columns(),
        sa.Column("price", sa.Numeric(18, 6), nullable=True),
        sa.Column("patrimonio_liq", sa.Numeric(24, 6), nullable=True),
        sa.Column("indice_replicado", sa.String(length=160), nullable=True),
        sa.Column("tipo", sa.String(length=80), nullable=True),
        sa.Column("taxa_adm", sa.Numeric(18, 6), nullable=True),
        sa.Column("retorno_12m", sa.Numeric(18, 6), nullable=True),
        sa.Column("retorno_24m", sa.Numeric(18, 6), nullable=True),
        sa.Column("tracking_error", sa.Numeric(18, 6), nullable=True),
        sa.Column("tracking_difference", sa.Numeric(18, 6), nullable=True),
        sa.Column("volume_medio_diario", sa.Numeric(24, 6), nullable=True),
        sa.Column("num_cotistas", sa.Integer(), nullable=True),
        sa.Column("gestora", sa.String(length=160), nullable=True),
        *_source_column(),
        sa.UniqueConstraint("ticker", "date", "source", name="uq_etf_fundamentals_ticker_date_source"),
    )
    op.create_index("ix_etf_fundamentals_ticker", "etf_fundamentals", ["ticker"])
    op.create_index("ix_etf_fundamentals_date", "etf_fundamentals", ["date"])
    op.create_index("ix_etf_fundamentals_indice_replicado", "etf_fundamentals", ["indice_replicado"])
    op.create_index("ix_etf_fundamentals_source", "etf_fundamentals", ["source"])

    op.create_table(
        "bdr_fundamentals",
        *_common_columns(),
        sa.Column("price", sa.Numeric(18, 6), nullable=True),
        sa.Column("market_cap", sa.Numeric(24, 6), nullable=True),
        sa.Column("empresa_subjacente", sa.String(length=255), nullable=True),
        sa.Column("ticker_original", sa.String(length=32), nullable=True),
        sa.Column("bolsa_origem", sa.String(length=80), nullable=True),
        sa.Column("pais_origem", sa.String(length=80), nullable=True),
        sa.Column("moeda_origem", sa.String(length=16), nullable=True),
        sa.Column("cotacao_cambio", sa.Numeric(18, 6), nullable=True),
        sa.Column("pl", sa.Numeric(18, 6), nullable=True),
        sa.Column("pvp", sa.Numeric(18, 6), nullable=True),
        sa.Column("dy_12m", sa.Numeric(18, 6), nullable=True),
        sa.Column("volume_medio_diario_brl", sa.Numeric(24, 6), nullable=True),
        sa.Column("nivel_bdr", sa.String(length=80), nullable=True),
        *_source_column(),
        sa.UniqueConstraint("ticker", "date", "source", name="uq_bdr_fundamentals_ticker_date_source"),
    )
    op.create_index("ix_bdr_fundamentals_ticker", "bdr_fundamentals", ["ticker"])
    op.create_index("ix_bdr_fundamentals_date", "bdr_fundamentals", ["date"])
    op.create_index("ix_bdr_fundamentals_ticker_original", "bdr_fundamentals", ["ticker_original"])
    op.create_index("ix_bdr_fundamentals_source", "bdr_fundamentals", ["source"])

    op.create_table(
        "cripto_fundamentals",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("coin_id", sa.String(length=120), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("price_brl", sa.Numeric(24, 8), nullable=True),
        sa.Column("price_usd", sa.Numeric(24, 8), nullable=True),
        sa.Column("market_cap_usd", sa.Numeric(30, 6), nullable=True),
        sa.Column("market_cap_rank", sa.Integer(), nullable=True),
        sa.Column("volume_24h_usd", sa.Numeric(30, 6), nullable=True),
        sa.Column("price_change_1h_pct", sa.Numeric(18, 6), nullable=True),
        sa.Column("price_change_24h_pct", sa.Numeric(18, 6), nullable=True),
        sa.Column("price_change_7d_pct", sa.Numeric(18, 6), nullable=True),
        sa.Column("price_change_30d_pct", sa.Numeric(18, 6), nullable=True),
        sa.Column("price_change_90d_pct", sa.Numeric(18, 6), nullable=True),
        sa.Column("price_change_1y_pct", sa.Numeric(18, 6), nullable=True),
        sa.Column("btc_dominance", sa.Numeric(18, 6), nullable=True),
        sa.Column("circulating_supply", sa.Numeric(30, 6), nullable=True),
        sa.Column("max_supply", sa.Numeric(30, 6), nullable=True),
        sa.Column("ath_price_usd", sa.Numeric(24, 8), nullable=True),
        sa.Column("ath_change_pct", sa.Numeric(18, 6), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("coletado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("coin_id", "date", name="uq_cripto_fundamentals_coin_id_date"),
    )
    op.create_index("ix_cripto_fundamentals_coin_id", "cripto_fundamentals", ["coin_id"])
    op.create_index("ix_cripto_fundamentals_ticker", "cripto_fundamentals", ["ticker"])
    op.create_index("ix_cripto_fundamentals_date", "cripto_fundamentals", ["date"])
    op.create_index("ix_cripto_fundamentals_source", "cripto_fundamentals", ["source"])


def downgrade() -> None:
    for table, indexes in (
        ("cripto_fundamentals", ["ix_cripto_fundamentals_source", "ix_cripto_fundamentals_date", "ix_cripto_fundamentals_ticker", "ix_cripto_fundamentals_coin_id"]),
        ("bdr_fundamentals", ["ix_bdr_fundamentals_source", "ix_bdr_fundamentals_ticker_original", "ix_bdr_fundamentals_date", "ix_bdr_fundamentals_ticker"]),
        ("etf_fundamentals", ["ix_etf_fundamentals_source", "ix_etf_fundamentals_indice_replicado", "ix_etf_fundamentals_date", "ix_etf_fundamentals_ticker"]),
        ("acoes_fundamentals", ["ix_acoes_fundamentals_source", "ix_acoes_fundamentals_setor", "ix_acoes_fundamentals_date", "ix_acoes_fundamentals_ticker"]),
        ("fii_fundamentals", ["ix_fii_fundamentals_source", "ix_fii_fundamentals_segmento", "ix_fii_fundamentals_date", "ix_fii_fundamentals_ticker"]),
    ):
        for index in indexes:
            op.drop_index(index, table_name=table)
        op.drop_table(table)
