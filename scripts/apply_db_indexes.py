
from __future__ import annotations

from db import pg_compat as dbcompat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_DIR = ROOT / "data" / "POSTGRES_RUNTIME_DISABLED"

INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_assets_ticker ON assets(ticker)",
    "CREATE INDEX IF NOT EXISTS idx_assets_asset_class ON assets(asset_class)",
    "CREATE INDEX IF NOT EXISTS idx_asset_prices_asset_date ON asset_prices(asset_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_asset_dividends_asset_date ON asset_dividends(asset_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_asset_scores_asset_calculated ON asset_scores(asset_id, calculated_at)",
    "CREATE INDEX IF NOT EXISTS idx_asset_rankings_class_score ON asset_rankings(asset_class, score_total)",
    "CREATE INDEX IF NOT EXISTS idx_backtest_equity_curve_run_date ON backtest_equity_curve(backtest_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_optimization_results_run ON optimization_results(run_id)",
)

def table_exists(conn: dbcompat.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None

def main() -> int:
    if not ROOT_DIR.exists():
        print(f"[ERROR] Banco não encontrado: {ROOT_DIR}")
        return 1
    created = []
    with dbcompat.connect(ROOT_DIR) as conn:
        for sql in INDEXES:
            table = sql.split(" ON ", 1)[1].split("(", 1)[0].strip()
            if not table_exists(conn, table):
                print(f"[SKIP] tabela ausente: {table}")
                continue
            conn.execute(sql)
            created.append(sql.split()[5])
        conn.commit()
    print(f"[OK] Índices verificados/criados: {len(created)}")
    for name in created:
        print(f" - {name}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
