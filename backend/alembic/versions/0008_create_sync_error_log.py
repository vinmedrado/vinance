"""create sync error log table

Revision ID: 0008_create_sync_error_log
Revises: 0007_create_sync_log
Create Date: 2026-06-09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_create_sync_error_log"
down_revision = "0007_create_sync_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_error_log",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("mercado", sa.String(length=32), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("tipo_erro", sa.String(length=32), nullable=False),
        sa.Column("erro", sa.Text(), nullable=False),
        sa.Column("segundos", sa.Float(), nullable=False, server_default="0"),
        sa.Column("processado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sync_error_log_run_id", "sync_error_log", ["run_id"])
    op.create_index("ix_sync_error_log_mercado", "sync_error_log", ["mercado"])
    op.create_index("ix_sync_error_log_ticker", "sync_error_log", ["ticker"])
    op.create_index("ix_sync_error_log_tipo_erro", "sync_error_log", ["tipo_erro"])


def downgrade() -> None:
    op.drop_index("ix_sync_error_log_tipo_erro", table_name="sync_error_log")
    op.drop_index("ix_sync_error_log_ticker", table_name="sync_error_log")
    op.drop_index("ix_sync_error_log_mercado", table_name="sync_error_log")
    op.drop_index("ix_sync_error_log_run_id", table_name="sync_error_log")
    op.drop_table("sync_error_log")
