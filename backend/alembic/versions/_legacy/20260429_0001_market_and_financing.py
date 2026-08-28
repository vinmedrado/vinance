"""FinanceOS patch 5.2 base schema

Revision ID: 20260429_0001
Revises:
Create Date: 2026-04-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260429_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("asset_class", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="BRL"),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=False, server_default="BR"),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("symbol", "asset_class", name="uq_assets_symbol_class"),
        sa.UniqueConstraint("ticker", "asset_class", name="uq_assets_ticker_class"),
    )
    op.create_index("ix_assets_id", "assets", ["id"])
    op.create_index("ix_assets_symbol", "assets", ["symbol"])
    op.create_index("ix_assets_ticker", "assets", ["ticker"])
    op.create_index("ix_assets_asset_class", "assets", ["asset_class"])

    op.create_table(
        "asset_prices",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close", sa.Float(), nullable=True),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("symbol", "date", "source", name="uq_asset_prices_symbol_date_source"),
    )
    op.create_index("ix_asset_prices_asset_id", "asset_prices", ["asset_id"])
    op.create_index("ix_asset_prices_symbol", "asset_prices", ["symbol"])
    op.create_index("ix_asset_prices_date", "asset_prices", ["date"])

    op.create_table(
        "asset_dividends",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="BRL"),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="yfinance"),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("symbol", "date", "amount", "source", name="uq_asset_dividends_symbol_date_amount_source"),
    )
    op.create_index("ix_asset_dividends_asset_id", "asset_dividends", ["asset_id"])
    op.create_index("ix_asset_dividends_symbol", "asset_dividends", ["symbol"])
    op.create_index("ix_asset_dividends_date", "asset_dividends", ["date"])
    op.create_index("ix_asset_dividends_symbol_date", "asset_dividends", ["symbol", "date"])

    op.create_table(
        "market_indices",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close", sa.Float(), nullable=True),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="yfinance"),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("symbol", "date", "source", name="uq_market_indices_symbol_date_source"),
    )
    op.create_index("ix_market_indices_symbol", "market_indices", ["symbol"])
    op.create_index("ix_market_indices_date", "market_indices", ["date"])

    op.create_table(
        "macro_indicators",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="BCB_SGS"),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_macro_indicators_code", "macro_indicators", ["code"])
    op.create_index("ix_macro_indicators_date", "macro_indicators", ["date"])

    op.create_table(
        "fixed_income_products",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("issuer", sa.String(length=160), nullable=False),
        sa.Column("product_type", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=220), nullable=False),
        sa.Column("indexer", sa.String(length=40), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("maturity_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("liquidity_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("guarantee_type", sa.String(length=80), nullable=True),
        sa.Column("minimum_investment", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="csv_manual"),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="BRL"),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "issuer", "product_type", "name", "maturity_date", name="uq_fixed_income_user_product"),
    )
    op.create_index("ix_fixed_income_products_user_id", "fixed_income_products", ["user_id"])
    op.create_index("ix_fixed_income_products_product_type", "fixed_income_products", ["product_type"])
    op.create_index("ix_fixed_income_user_type", "fixed_income_products", ["user_id", "product_type"])

    op.create_table(
        "portfolio_positions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("asset_class", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("average_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="BRL"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_portfolio_positions_user_id", "portfolio_positions", ["user_id"])
    op.create_index("ix_portfolio_positions_asset_id", "portfolio_positions", ["asset_id"])
    op.create_index("ix_portfolio_positions_symbol", "portfolio_positions", ["symbol"])
    op.create_index("ix_portfolio_positions_asset_class", "portfolio_positions", ["asset_class"])
    op.create_index("ix_portfolio_positions_user_symbol", "portfolio_positions", ["user_id", "symbol"])

    op.create_table(
        "data_sync_logs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("entity", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
    )
    op.create_index("ix_data_sync_logs_source", "data_sync_logs", ["source"])
    op.create_index("ix_data_sync_logs_entity", "data_sync_logs", ["entity"])
    op.create_index("ix_data_sync_logs_status", "data_sync_logs", ["status"])
    op.create_index("ix_data_sync_logs_source_entity", "data_sync_logs", ["source", "entity"])

    # Mantém compatibilidade com os demais models já existentes no backend.
    from backend.app.database import Base
    import backend.app.models  # noqa: F401

    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    for table_name in (
        "data_sync_logs",
        "portfolio_positions",
        "fixed_income_products",
        "macro_indicators",
        "market_indices",
        "asset_dividends",
        "asset_prices",
        "assets",
    ):
        op.drop_table(table_name)
