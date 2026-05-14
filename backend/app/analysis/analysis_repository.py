from __future__ import annotations

import json
from db import pg_compat as dbcompat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
ROOT_DIR = ROOT / "data" / "POSTGRES_RUNTIME_DISABLED"

ANALYSIS_TABLE_SQL = [
    """
    CREATE TABLE IF NOT EXISTS asset_analysis_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id INTEGER NOT NULL,
        ticker VARCHAR(32) NOT NULL,
        asset_class VARCHAR(32),
        as_of_date DATETIME NOT NULL,
        metrics_json TEXT NOT NULL,
        quality_status VARCHAR(32) NOT NULL DEFAULT 'ok',
        quality_message TEXT,
        calculated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(asset_id, as_of_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS asset_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id INTEGER NOT NULL,
        ticker VARCHAR(32) NOT NULL,
        asset_class VARCHAR(32),
        score_total FLOAT,
        score_retorno FLOAT,
        score_risco FLOAT,
        score_liquidez FLOAT,
        score_dividendos FLOAT,
        score_tendencia FLOAT,
        explanation TEXT,
        calculated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(asset_id, calculated_at)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS asset_rankings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id INTEGER NOT NULL,
        ticker VARCHAR(32) NOT NULL,
        asset_class VARCHAR(32) NOT NULL,
        ranking_type VARCHAR(64) NOT NULL,
        rank_position INTEGER NOT NULL,
        score_value FLOAT,
        calculated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(asset_class, ranking_type, rank_position, calculated_at)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS analysis_run_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pipeline_name VARCHAR(120) NOT NULL DEFAULT 'analysis_engine',
        status VARCHAR(32) NOT NULL,
        started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        finished_at DATETIME,
        total_assets INTEGER NOT NULL DEFAULT 0,
        total_success INTEGER NOT NULL DEFAULT 0,
        total_failed INTEGER NOT NULL DEFAULT 0,
        total_skipped INTEGER NOT NULL DEFAULT 0,
        error_message TEXT,
        payload_json TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_asset_analysis_metrics_asset ON asset_analysis_metrics(asset_id)",
    "CREATE INDEX IF NOT EXISTS ix_asset_scores_ticker ON asset_scores(ticker)",
    "CREATE INDEX IF NOT EXISTS ix_asset_rankings_class_type ON asset_rankings(asset_class, ranking_type)",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_connection(db_path: Path | None = None) -> dbcompat.Connection:
    conn = dbcompat.connect(db_path or ROOT_DIR)
    conn.row_factory = dbcompat.Row
    return conn


def ensure_analysis_schema(conn: dbcompat.Connection) -> None:
    for sql in ANALYSIS_TABLE_SQL:
        conn.execute(sql)


def fetch_assets(conn: dbcompat.Connection, asset_class: str = "all", tickers: list[str] | None = None, limit: int | None = None) -> list[dbcompat.Row]:
    where = ["COALESCE(is_active, 1) = 1"]
    params: list[Any] = []
    if asset_class and asset_class != "all":
        where.append("asset_class = ?")
        params.append(asset_class)
    if tickers:
        placeholders = ",".join("?" for _ in tickers)
        where.append(f"ticker IN ({placeholders})")
        params.extend([t.strip().upper() for t in tickers if t.strip()])
    sql = "SELECT id, ticker, COALESCE(name, ticker) AS name, asset_class, country, currency FROM assets WHERE " + " AND ".join(where) + " ORDER BY ticker"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return conn.execute(sql, params).fetchall()


def fetch_prices(conn: dbcompat.Connection, asset_id: int) -> list[dbcompat.Row]:
    return conn.execute(
        """
        SELECT date, open, high, low, close, adjusted_close, volume
        FROM asset_prices
        WHERE asset_id = ? AND close IS NOT NULL
        ORDER BY date ASC
        """,
        (asset_id,),
    ).fetchall()


def fetch_dividends(conn: dbcompat.Connection, asset_id: int) -> list[dbcompat.Row]:
    return conn.execute(
        """
        SELECT COALESCE(payment_date, ex_date, date) AS date, amount
        FROM asset_dividends
        WHERE asset_id = ? AND amount IS NOT NULL
        ORDER BY date ASC
        """,
        (asset_id,),
    ).fetchall()


def save_metrics(conn: dbcompat.Connection, asset: dbcompat.Row, metrics: dict[str, Any], quality_status: str = "ok", quality_message: str | None = None) -> None:
    as_of_date = metrics.get("as_of_date") or now_iso()
    conn.execute(
        """
        INSERT OR REPLACE INTO asset_analysis_metrics
        (asset_id, ticker, asset_class, as_of_date, metrics_json, quality_status, quality_message, calculated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (asset["id"], asset["ticker"], asset["asset_class"], as_of_date, json.dumps(metrics, ensure_ascii=False), quality_status, quality_message),
    )


def save_score(conn: dbcompat.Connection, asset: dbcompat.Row, score: dict[str, Any], calculated_at: str) -> None:
    conn.execute(
        """
        INSERT INTO asset_scores
        (asset_id, ticker, asset_class, score_total, score_retorno, score_risco, score_liquidez, score_dividendos, score_tendencia, explanation, calculated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            asset["id"], asset["ticker"], asset["asset_class"], score.get("score_total"), score.get("score_retorno"),
            score.get("score_risco"), score.get("score_liquidez"), score.get("score_dividendos"), score.get("score_tendencia"),
            score.get("explanation"), calculated_at,
        ),
    )


def save_rankings(conn: dbcompat.Connection, scores: list[dict[str, Any]], top_n: int, calculated_at: str) -> None:
    ranking_fields = {
        "score_total": "score_total",
        "score_retorno": "score_retorno",
        "score_risco": "score_risco",
        "score_dividendos": "score_dividendos",
        "score_liquidez": "score_liquidez",
    }
    by_class: dict[str, list[dict[str, Any]]] = {}
    for item in scores:
        if item.get("score_total") is None:
            continue
        by_class.setdefault(item["asset_class"] or "unknown", []).append(item)
    for asset_class, rows in by_class.items():
        for ranking_type, field in ranking_fields.items():
            ranked = sorted([r for r in rows if r.get(field) is not None], key=lambda r: r[field], reverse=True)[:top_n]
            for pos, row in enumerate(ranked, start=1):
                conn.execute(
                    """
                    INSERT INTO asset_rankings
                    (asset_id, ticker, asset_class, ranking_type, rank_position, score_value, calculated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (row["asset_id"], row["ticker"], asset_class, ranking_type, pos, row.get(field), calculated_at),
                )


def log_run(conn: dbcompat.Connection, status: str, started_at: str, total_assets: int, total_success: int, total_failed: int, total_skipped: int, error_message: str | None = None, payload: dict[str, Any] | None = None) -> None:
    conn.execute(
        """
        INSERT INTO analysis_run_logs
        (pipeline_name, status, started_at, finished_at, total_assets, total_success, total_failed, total_skipped, error_message, payload_json)
        VALUES ('analysis_engine', ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)
        """,
        (status, started_at, total_assets, total_success, total_failed, total_skipped, error_message, json.dumps(payload or {}, ensure_ascii=False)),
    )
