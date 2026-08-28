"""create sync log table

Revision ID: 0007_create_sync_log
Revises: 0006_create_ml_features_tables
Create Date: 2026-06-09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_create_sync_log"
down_revision = "0006_create_ml_features_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_log",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("mercado", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ok", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("erros", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sucesso_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tempo_segundos", sa.Float(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_sync_log_run_id", "sync_log", ["run_id"])
    op.create_index("ix_sync_log_source", "sync_log", ["source"])
    op.create_index("ix_sync_log_mercado", "sync_log", ["mercado"])
    op.create_index("ix_sync_log_status", "sync_log", ["status"])


def downgrade() -> None:
    op.drop_index("ix_sync_log_status", table_name="sync_log")
    op.drop_index("ix_sync_log_mercado", table_name="sync_log")
    op.drop_index("ix_sync_log_source", table_name="sync_log")
    op.drop_index("ix_sync_log_run_id", table_name="sync_log")
    op.drop_table("sync_log")
