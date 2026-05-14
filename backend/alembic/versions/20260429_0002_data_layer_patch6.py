"""FinanceOS PATCH 6 data layer columns and indexes

Revision ID: 20260429_0002
Revises: 20260429_0001
Create Date: 2026-04-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260429_0002"
down_revision = "20260429_0001"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {col["name"] for col in inspector.get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(table_name):
        op.add_column(table_name, column)


def upgrade() -> None:
    # Asset prices: PATCH 6 stores OHLCV, adjusted close and update timestamp.
    _add_column_if_missing("asset_prices", sa.Column("open", sa.Float(), nullable=True))
    _add_column_if_missing("asset_prices", sa.Column("high", sa.Float(), nullable=True))
    _add_column_if_missing("asset_prices", sa.Column("low", sa.Float(), nullable=True))
    _add_column_if_missing("asset_prices", sa.Column("adjusted_close", sa.Float(), nullable=True))
    _add_column_if_missing("asset_prices", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    # Dividends: preserve old date column and add explicit fields for providers that expose them.
    _add_column_if_missing("asset_dividends", sa.Column("ex_date", sa.DateTime(timezone=True), nullable=True))
    _add_column_if_missing("asset_dividends", sa.Column("payment_date", sa.DateTime(timezone=True), nullable=True))

    # Logs: keep old source/entity/message fields and add names requested by data-layer scripts.
    _add_column_if_missing("data_sync_logs", sa.Column("pipeline_name", sa.String(length=120), nullable=True))
    _add_column_if_missing("data_sync_logs", sa.Column("error_message", sa.Text(), nullable=True))

    op.create_index("ix_asset_prices_asset_date", "asset_prices", ["asset_id", "date"], unique=False, if_not_exists=True)
    op.create_index("ix_asset_prices_symbol_date_source", "asset_prices", ["symbol", "date", "source"], unique=False, if_not_exists=True)
    op.create_index("ix_macro_indicators_name_date", "macro_indicators", ["name", "date"], unique=False, if_not_exists=True)
    op.create_index("ix_data_sync_logs_pipeline_name", "data_sync_logs", ["pipeline_name"], unique=False, if_not_exists=True)


def downgrade() -> None:
    # SQLite cannot reliably drop columns on older versions. Keep columns to avoid data loss.
    op.drop_index("ix_data_sync_logs_pipeline_name", table_name="data_sync_logs", if_exists=True)
    op.drop_index("ix_macro_indicators_name_date", table_name="macro_indicators", if_exists=True)
    op.drop_index("ix_asset_prices_symbol_date_source", table_name="asset_prices", if_exists=True)
    op.drop_index("ix_asset_prices_asset_date", table_name="asset_prices", if_exists=True)
