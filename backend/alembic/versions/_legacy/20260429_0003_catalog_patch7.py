"""FinanceOS PATCH 7 catalog columns

Revision ID: 20260429_0003
Revises: 20260429_0002
Create Date: 2026-04-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260429_0003"
down_revision = "20260429_0002"
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
    _add_column_if_missing("assets", sa.Column("exchange", sa.String(length=32), nullable=True))
    _add_column_if_missing("assets", sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"))
    op.create_index("ix_assets_asset_class", "assets", ["asset_class"], unique=False, if_not_exists=True)
    op.create_index("ix_assets_country", "assets", ["country"], unique=False, if_not_exists=True)
    op.create_index("ix_assets_is_active", "assets", ["is_active"], unique=False, if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_assets_is_active", table_name="assets", if_exists=True)
    op.drop_index("ix_assets_country", table_name="assets", if_exists=True)
    op.drop_index("ix_assets_asset_class", table_name="assets", if_exists=True)
