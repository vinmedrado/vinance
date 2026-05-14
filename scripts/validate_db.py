from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import pg_compat as dbcompat
from pathlib import Path

from backend.app.data_layer.repositories.sqlite_repository import ensure_patch6_schema
from backend.app.data_layer.catalog.catalog_repository import ensure_catalog_schema
from backend.app.analysis.analysis_repository import ensure_analysis_schema
from backend.app.backtest.backtest_repository import BacktestRepository
from services.asset_catalog_db import ensure_asset_catalog_schema

ROOT_DIR = ROOT / "data" / "POSTGRES_RUNTIME_DISABLED"

REQUIRED_SCHEMA = {
    "asset_catalog": ["id", "ticker", "yahoo_symbol", "name", "asset_class", "market", "currency", "source", "api_status", "last_validated_at", "notes", "created_at", "updated_at"],
    "assets": ["id", "ticker", "name", "asset_class", "country", "last_updated_at", "created_at", "updated_at", "exchange", "is_active"],
    "asset_prices": ["id", "asset_id", "symbol", "date", "open", "high", "low", "close", "adjusted_close", "volume", "source", "created_at"],
    "asset_dividends": ["id", "asset_id", "symbol", "date", "ex_date", "payment_date", "amount", "source", "created_at"],
    "market_indices": ["id", "symbol", "name", "date", "close", "source", "created_at"],
    "macro_indicators": ["id", "code", "name", "date", "value", "source", "created_at"],
    "fixed_income_products": ["id", "issuer", "product_type", "name", "indexer", "rate", "created_at", "updated_at"],
    "portfolio_positions": ["id", "user_id", "asset_id", "symbol", "asset_class", "quantity", "average_price", "created_at", "updated_at"],
    "data_sync_logs": ["id", "pipeline_name", "source", "entity", "status", "started_at", "finished_at", "rows_inserted", "rows_updated", "rows_skipped", "error_message"],
    "asset_analysis_metrics": ["id", "asset_id", "ticker", "asset_class", "as_of_date", "metrics_json", "quality_status", "calculated_at"],
    "asset_scores": ["id", "asset_id", "ticker", "asset_class", "score_total", "score_retorno", "score_risco", "score_liquidez", "score_dividendos", "score_tendencia", "explanation", "calculated_at"],
    "asset_rankings": ["id", "asset_id", "ticker", "asset_class", "ranking_type", "rank_position", "score_value", "calculated_at"],
    "analysis_run_logs": ["id", "pipeline_name", "status", "started_at", "finished_at", "total_assets", "total_success", "total_failed", "total_skipped"],
    "backtest_runs": ["id", "strategy_name", "start_date", "end_date", "initial_capital", "created_at"],
    "backtest_trades": ["id", "backtest_id", "ticker", "action", "date", "price", "quantity"],
    "backtest_positions": ["id", "backtest_id", "ticker", "quantity", "avg_price", "last_updated"],
    "backtest_equity_curve": ["id", "backtest_id", "date", "equity_value"],
    "backtest_metrics": ["id", "backtest_id", "total_return", "annual_return", "max_drawdown", "sharpe_ratio", "win_rate", "total_trades"],
}


def table_columns(conn: dbcompat.Connection, table: str) -> dict[str, str]:
    return {row[1]: (row[2] or "").upper() for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def main() -> int:
    print("=" * 80)
    print("FinanceOS DB Auditor - PATCH 6")
    print("=" * 80)
    print(f"Banco: {ROOT_DIR}")
    if not ROOT_DIR.exists():
        print("[CRITICO] Banco não encontrado.")
        return 1

    critical_errors: list[str] = []
    with dbcompat.connect(ROOT_DIR) as conn:
        conn.row_factory = dbcompat.Row
        conn.execute("PRAGMA foreign_keys = ON")
        ensure_patch6_schema(conn)
        ensure_asset_catalog_schema(conn)
        ensure_catalog_schema(conn)
        ensure_analysis_schema(conn)
        BacktestRepository(conn=conn).ensure_schema()
        conn.commit()

        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        for table, required_columns in REQUIRED_SCHEMA.items():
            if table not in tables:
                critical_errors.append(f"Tabela ausente após autocorreção: {table}")
                print(f"[ERRO] {table}: tabela ausente")
                continue
            columns = table_columns(conn, table)
            missing = [col for col in required_columns if col not in columns]
            if missing:
                critical_errors.append(f"{table}: colunas ausentes {missing}")
                print(f"[ERRO] {table}: faltando {missing}")
            else:
                print(f"[OK] {table}: {len(columns)} colunas")

        checks = [
            ("asset_prices", "close < 0", "preços negativos"),
            ("asset_prices", "volume < 0", "volumes negativos"),
            ("market_indices", "close < 0", "índices com close negativo"),
            ("macro_indicators", "date(date) > date('now')", "macro com data futura"),
            ("asset_prices", "date(date) > date('now')", "preços com data futura"),
        ]
        for table, condition, label in checks:
            if table in tables:
                count = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {condition}").fetchone()[0]
                if count:
                    critical_errors.append(f"{label}: {count}")
                    print(f"[ERRO] {label}: {count}")

    if critical_errors:
        print("\nResultado: ERRO CRÍTICO")
        for err in critical_errors:
            print(f"- {err}")
        return 1
    print("\nResultado: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
