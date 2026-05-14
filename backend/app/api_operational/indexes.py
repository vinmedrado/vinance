
from __future__ import annotations

import logging
from db import pg_compat as dbcompat

logger = logging.getLogger("financeos.api")

INDEXES: tuple[tuple[str, str], ...] = (
    ("idx_assets_ticker", "CREATE INDEX IF NOT EXISTS idx_assets_ticker ON assets(ticker)"),
    ("idx_assets_asset_class", "CREATE INDEX IF NOT EXISTS idx_assets_asset_class ON assets(asset_class)"),
    ("idx_asset_prices_asset_date", "CREATE INDEX IF NOT EXISTS idx_asset_prices_asset_date ON asset_prices(asset_id, date)"),
    ("idx_asset_dividends_asset_date", "CREATE INDEX IF NOT EXISTS idx_asset_dividends_asset_date ON asset_dividends(asset_id, date)"),
    ("idx_asset_scores_asset_calculated", "CREATE INDEX IF NOT EXISTS idx_asset_scores_asset_calculated ON asset_scores(asset_id, calculated_at)"),
    ("idx_asset_rankings_class_score", "CREATE INDEX IF NOT EXISTS idx_asset_rankings_class_score ON asset_rankings(asset_class, score_total)"),
    ("idx_backtest_equity_curve_run_date", "CREATE INDEX IF NOT EXISTS idx_backtest_equity_curve_run_date ON backtest_equity_curve(backtest_id, date)"),
    ("idx_optimization_results_run", "CREATE INDEX IF NOT EXISTS idx_optimization_results_run ON optimization_results(run_id)"),
)

def _table_exists(conn: dbcompat.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None

def ensure_indexes(conn: dbcompat.Connection) -> list[str]:
    created_or_existing: list[str] = []
    for name, sql in INDEXES:
        table = sql.split(" ON ", 1)[1].split("(", 1)[0].strip()
        if not _table_exists(conn, table):
            continue
        try:
            conn.execute(sql)
            created_or_existing.append(name)
        except dbcompat.DatabaseError as exc:
            logger.warning("index_creation_failed", extra={"index": name, "error": str(exc)})
    conn.commit()
    return created_or_existing
