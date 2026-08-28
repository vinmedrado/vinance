"""create asset catalog

Revision ID: 0003_create_asset_catalog
Revises: 0002_create_financial_tables
Create Date: 2026-06-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_create_asset_catalog"
down_revision = "0002_create_financial_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_catalog",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("sector", sa.String(length=120), nullable=True),
        sa.Column("segment", sa.String(length=120), nullable=True),
        sa.Column("currency", sa.String(length=12), nullable=False, server_default="BRL"),
        sa.Column("exchange", sa.String(length=80), nullable=True),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("ticker", "market", name="uq_asset_catalog_ticker_market"),
    )
    op.create_index("ix_asset_catalog_market", "asset_catalog", ["market"])
    op.create_index("ix_asset_catalog_ticker", "asset_catalog", ["ticker"])
    op.create_index("ix_asset_catalog_is_active", "asset_catalog", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_asset_catalog_is_active", table_name="asset_catalog")
    op.drop_index("ix_asset_catalog_ticker", table_name="asset_catalog")
    op.drop_index("ix_asset_catalog_market", table_name="asset_catalog")
    op.drop_table("asset_catalog")
