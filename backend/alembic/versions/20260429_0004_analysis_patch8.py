"""PATCH 8 - analysis engine tables

Revision ID: 20260429_0004
Revises: 20260429_0003
Create Date: 2026-04-29
"""
from alembic import op
import sqlalchemy as sa

revision = "20260429_0004"
down_revision = "20260429_0003"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "asset_analysis_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(32), nullable=False),
        sa.Column("asset_class", sa.String(32), nullable=True),
        sa.Column("as_of_date", sa.DateTime(), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False),
        sa.Column("quality_status", sa.String(32), nullable=False, server_default="ok"),
        sa.Column("quality_message", sa.Text(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_asset_analysis_metrics_asset", "asset_analysis_metrics", ["asset_id"])
    op.create_table(
        "asset_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(32), nullable=False),
        sa.Column("asset_class", sa.String(32), nullable=True),
        sa.Column("score_total", sa.Float(), nullable=True),
        sa.Column("score_retorno", sa.Float(), nullable=True),
        sa.Column("score_risco", sa.Float(), nullable=True),
        sa.Column("score_liquidez", sa.Float(), nullable=True),
        sa.Column("score_dividendos", sa.Float(), nullable=True),
        sa.Column("score_tendencia", sa.Float(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_asset_scores_ticker", "asset_scores", ["ticker"])
    op.create_table(
        "asset_rankings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(32), nullable=False),
        sa.Column("asset_class", sa.String(32), nullable=False),
        sa.Column("ranking_type", sa.String(64), nullable=False),
        sa.Column("rank_position", sa.Integer(), nullable=False),
        sa.Column("score_value", sa.Float(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_asset_rankings_class_type", "asset_rankings", ["asset_class", "ranking_type"])
    op.create_table(
        "analysis_run_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pipeline_name", sa.String(120), nullable=False, server_default="analysis_engine"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("total_assets", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_success", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
    )

def downgrade() -> None:
    op.drop_table("analysis_run_logs")
    op.drop_index("ix_asset_rankings_class_type", table_name="asset_rankings")
    op.drop_table("asset_rankings")
    op.drop_index("ix_asset_scores_ticker", table_name="asset_scores")
    op.drop_table("asset_scores")
    op.drop_index("ix_asset_analysis_metrics_asset", table_name="asset_analysis_metrics")
    op.drop_table("asset_analysis_metrics")
