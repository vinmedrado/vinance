"""PATCH 12 - hardening indexes

Revision ID: 20260429_0007
Revises: 20260429_0006
Create Date: 2026-04-29
"""
from alembic import op

revision = '20260429_0007'
down_revision = '20260429_0006'
branch_labels = None
depends_on = None


def upgrade():
    # Índices seguros e idempotentes para SQLite. Não alteram dados nem lógica das engines.
    op.execute("CREATE INDEX IF NOT EXISTS idx_assets_ticker ON assets(ticker)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_assets_asset_class ON assets(asset_class)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_asset_prices_asset_date ON asset_prices(asset_id, date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_asset_dividends_asset_date ON asset_dividends(asset_id, date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_asset_scores_asset_calculated ON asset_scores(asset_id, calculated_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_asset_rankings_class_score ON asset_rankings(asset_class, score_total)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_backtest_equity_curve_run_date ON backtest_equity_curve(backtest_id, date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_optimization_results_run ON optimization_results(run_id)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_optimization_results_run")
    op.execute("DROP INDEX IF EXISTS idx_backtest_equity_curve_run_date")
    op.execute("DROP INDEX IF EXISTS idx_asset_rankings_class_score")
    op.execute("DROP INDEX IF EXISTS idx_asset_scores_asset_calculated")
    op.execute("DROP INDEX IF EXISTS idx_asset_dividends_asset_date")
    op.execute("DROP INDEX IF EXISTS idx_asset_prices_asset_date")
    op.execute("DROP INDEX IF EXISTS idx_assets_asset_class")
    op.execute("DROP INDEX IF EXISTS idx_assets_ticker")
