
from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter
from backend.app.api_operational.cache import cache_stats
from backend.app.api_operational.db import connect, table_exists
from backend.app.core.hardening import get_uptime_seconds

router = APIRouter()

REQUIRED_TABLES = [
    "assets", "asset_prices", "asset_dividends", "market_indices", "macro_indicators",
    "data_sync_logs", "asset_scores", "asset_rankings", "asset_analysis_metrics",
    "backtest_runs", "optimization_runs",
]

def _last_data_update(conn) -> str | None:
    candidates = [
        ("data_sync_logs", "finished_at"),
        ("asset_scores", "calculated_at"),
        ("assets", "updated_at"),
    ]
    for table, col in candidates:
        if table_exists(conn, table):
            cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            if col in cols:
                row = conn.execute(f"SELECT MAX({col}) AS last_update FROM {table}").fetchone()
                if row and row["last_update"]:
                    return row["last_update"]
    return None

@router.get("/health")
def health() -> dict:
    try:
        with connect() as conn:
            conn.execute("SELECT 1").fetchone()
        db_status = "connected"
    except Exception:
        db_status = "error"
    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "service": "FinanceOS API",
        "database": db_status,
        "uptime_seconds": get_uptime_seconds(),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

@router.get("/system/status")
def system_status() -> dict:
    try:
        with connect() as conn:
            tables = {name: table_exists(conn, name) for name in REQUIRED_TABLES}
            pipeline_status = []
            if table_exists(conn, "data_sync_logs"):
                pipeline_status = [dict(r) for r in conn.execute(
                    "SELECT * FROM data_sync_logs ORDER BY COALESCE(finished_at, started_at, created_at, id) DESC LIMIT 10"
                ).fetchall()]
            return {
                "status": "ok",
                "database": "connected",
                "uptime_seconds": get_uptime_seconds(),
                "last_data_update": _last_data_update(conn),
                "cache": cache_stats(),
                "required_tables": tables,
                "missing_tables": [k for k, v in tables.items() if not v],
                "recent_pipeline_logs": pipeline_status,
            }
    except Exception as exc:
        return {"status": "degraded", "database": "error", "error": "Falha controlada ao consultar status do sistema"}
