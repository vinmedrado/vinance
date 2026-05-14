from __future__ import annotations

from db import pg_compat as dbcompat
from datetime import datetime, timezone
from typing import Any

SUPPORTED_CLASSES = {"equity", "fii", "etf", "bdr", "crypto", "index", "currency", "commodity"}
QUALITY_COLUMNS = {
    "data_quality_score": "REAL DEFAULT 0",
    "history_days": "INTEGER DEFAULT 0",
    "first_price_date": "TEXT",
    "last_price_date": "TEXT",
    "price_records": "INTEGER DEFAULT 0",
    "validation_score": "REAL DEFAULT 0",
    "reliability_status": "TEXT DEFAULT 'unknown'",
    "recommendation_tag": "TEXT",
    "updated_quality_at": "TEXT",
    "preferred_source": "TEXT",
    "last_source_used": "TEXT",
    "source_priority": "TEXT",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_asset_quality_columns(conn: dbcompat.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS asset_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            yahoo_symbol TEXT,
            name TEXT,
            asset_class TEXT NOT NULL,
            market TEXT,
            currency TEXT,
            source TEXT,
            api_status TEXT NOT NULL DEFAULT 'pending_validation',
            last_validated_at TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, asset_class)
        )
        """
    )
    cols = {row[1] for row in conn.execute("PRAGMA table_info(asset_catalog)").fetchall()}
    for col, ddl in QUALITY_COLUMNS.items():
        if col not in cols:
            conn.execute(f"ALTER TABLE asset_catalog ADD COLUMN {col} {ddl}")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_asset_catalog_quality ON asset_catalog(data_quality_score DESC, reliability_status, recommendation_tag)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_asset_catalog_quality_class ON asset_catalog(asset_class, data_quality_score DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_asset_catalog_source_quality ON asset_catalog(last_source_used, api_status, reliability_status)")
    conn.commit()


def _parse_date(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value)[:19].replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:len(fmt)], fmt)
        except Exception:
            pass
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def get_asset_price_stats(conn: dbcompat.Connection, ticker: str) -> dict[str, Any]:
    ticker_norm = str(ticker or "").upper().replace(".SA", "")
    if not ticker_norm:
        return {"price_records": 0, "first_price_date": None, "last_price_date": None, "history_days": 0}
    row = None
    try:
        row = conn.execute(
            """
            SELECT MIN(p.date), MAX(p.date), COUNT(*)
              FROM asset_prices p
              LEFT JOIN assets a ON a.id = p.asset_id
             WHERE UPPER(REPLACE(COALESCE(a.ticker, a.symbol, p.symbol), '.SA', '')) = ?
                OR UPPER(REPLACE(COALESCE(p.symbol, ''), '.SA', '')) = ?
            """,
            (ticker_norm, ticker_norm),
        ).fetchone()
    except Exception:
        row = conn.execute(
            """
            SELECT MIN(date), MAX(date), COUNT(*)
              FROM asset_prices
             WHERE UPPER(REPLACE(COALESCE(symbol, ''), '.SA', '')) = ?
            """,
            (ticker_norm,),
        ).fetchone()
    first_date, last_date, count = row if row else (None, None, 0)
    first_dt = _parse_date(first_date)
    last_dt = _parse_date(last_date)
    history_days = max((last_dt - first_dt).days, 0) if first_dt and last_dt else 0
    return {
        "first_price_date": str(first_date)[:10] if first_date else None,
        "last_price_date": str(last_date)[:10] if last_date else None,
        "price_records": int(count or 0),
        "history_days": int(history_days),
    }


def classify_reliability(score: float, history_days: int, price_records: int, api_status: str) -> str:
    status = (api_status or "").lower()
    if status in {"not_found", "unsupported"}:
        return "invalid"
    if status == "error" and score < 35:
        return "unknown"
    if status != "active" and score < 45:
        return "unknown"
    if history_days < 180 or price_records < 100:
        return "weak_data" if status == "active" else "unknown"
    if score >= 80 and history_days >= 3 * 365 and price_records >= 500:
        return "excellent"
    if score >= 65 and history_days >= 365 and price_records >= 180:
        return "good"
    if score >= 45:
        return "usable"
    return "weak_data" if status in {"active", "weak_data", "stale"} else "unknown"


def recommendation_from_quality(reliability_status: str, asset_class: str) -> str:
    rel = (reliability_status or "unknown").lower()
    if rel in {"excellent", "good"}:
        return "recommended"
    if rel == "usable":
        return "watchlist"
    if rel in {"weak_data", "invalid"}:
        return "avoid"
    return "pending"


def calculate_asset_quality(asset: dict[str, Any], price_stats: dict[str, Any]) -> dict[str, Any]:
    api_status = str(asset.get("api_status") or "unknown").lower()
    asset_class = str(asset.get("asset_class") or "unknown").lower()
    history_days = int(price_stats.get("history_days") or 0)
    price_records = int(price_stats.get("price_records") or 0)
    last_price_date = price_stats.get("last_price_date")
    score = 0.0
    validation_score = 0.0

    # Status/API: até 25 pts. Não-active nunca passa de 40 no score final.
    if api_status == "active":
        score += 25
        validation_score = 100
    elif api_status == "weak_data":
        score += 14
        validation_score = 65
    elif api_status == "stale":
        score += 10
        validation_score = 45
    elif api_status == "pending_validation":
        score += 5
        validation_score = 30
    elif api_status == "error":
        score += 3
        validation_score = 20
    else:
        validation_score = 5

    # Histórico em dias: até 35 pts; > 3 anos pesa mais que simples contagem.
    if history_days >= 3 * 365:
        score += 35
    elif history_days >= 2 * 365:
        score += 28
    elif history_days >= 365:
        score += 20
    elif history_days >= 180:
        score += 10
    elif history_days > 0:
        score += 4

    # Registros: até 20 pts.
    if price_records >= 750:
        score += 20
    elif price_records >= 500:
        score += 17
    elif price_records >= 250:
        score += 12
    elif price_records >= 100:
        score += 7
    elif price_records > 0:
        score += 2

    # Recência: até 15 pts com penalização forte para dados antigos.
    recency_pts = 0
    if last_price_date:
        last_dt = _parse_date(last_price_date)
        if last_dt:
            age_days = max((datetime.utcnow() - last_dt).days, 0)
            if age_days <= 10:
                recency_pts = 15
            elif age_days <= 30:
                recency_pts = 12
            elif age_days <= 90:
                recency_pts = 7
            elif age_days <= 180:
                recency_pts = 3
            else:
                recency_pts = -10
    score += recency_pts

    if asset_class in SUPPORTED_CLASSES:
        score += 5

    if api_status != "active":
        score = min(score, 40)
    if history_days < 180:
        score = min(score, 44)
    if price_records < 100:
        score = min(score, 44)

    score = round(max(0.0, min(score, 100.0)), 2)
    rel = classify_reliability(score, history_days, price_records, api_status)
    rec = recommendation_from_quality(rel, asset_class)
    return {
        "data_quality_score": score,
        "history_days": history_days,
        "first_price_date": price_stats.get("first_price_date"),
        "last_price_date": price_stats.get("last_price_date"),
        "price_records": price_records,
        "validation_score": round(validation_score, 2),
        "reliability_status": rel,
        "recommendation_tag": rec,
        "updated_quality_at": now_iso(),
    }


def update_asset_quality(conn: dbcompat.Connection, asset_id: int, quality: dict[str, Any]) -> None:
    ensure_asset_quality_columns(conn)
    conn.execute(
        """
        UPDATE asset_catalog
           SET data_quality_score=?,
               history_days=?,
               first_price_date=?,
               last_price_date=?,
               price_records=?,
               validation_score=?,
               reliability_status=?,
               recommendation_tag=?,
               updated_quality_at=?,
               updated_at=CURRENT_TIMESTAMP
         WHERE id=?
        """,
        (
            quality.get("data_quality_score", 0),
            quality.get("history_days", 0),
            quality.get("first_price_date"),
            quality.get("last_price_date"),
            quality.get("price_records", 0),
            quality.get("validation_score", 0),
            quality.get("reliability_status", "unknown"),
            quality.get("recommendation_tag", "pending"),
            quality.get("updated_quality_at") or now_iso(),
            asset_id,
        ),
    )
