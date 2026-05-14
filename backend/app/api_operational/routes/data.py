from __future__ import annotations

from fastapi import APIRouter, Query
from backend.app.api_operational.cache import ttl_cache
from backend.app.api_operational.db import connect, rows_to_dicts, safe_limit, safe_offset, table_exists, columns, pick

router = APIRouter()

def asset_id_for_ticker(conn, ticker: str):
    if not table_exists(conn, "assets"):
        return None
    cols = columns(conn, "assets")
    if "id" not in cols or "ticker" not in cols:
        return None
    row = conn.execute("SELECT id FROM assets WHERE UPPER(ticker)=UPPER(?) LIMIT 1", (ticker,)).fetchone()
    return row["id"] if row else None

@router.get("/coverage")
@ttl_cache(ttl_seconds=60)
def data_coverage(limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0)) -> dict:
    with connect() as conn:
        if not table_exists(conn, "assets"):
            return {"items": [], "summary": {"assets_with_prices": 0, "assets_without_prices": 0}}
        asset_cols = columns(conn, "assets")
        price_cols = columns(conn, "asset_prices")
        div_cols = columns(conn, "asset_dividends")
        ticker_expr = "a.ticker" if "ticker" in asset_cols else "a.id"
        if table_exists(conn, "asset_prices") and "asset_id" in price_cols and "date" in price_cols:
            sql = f"""
                SELECT {ticker_expr} AS ticker, MIN(p.date) AS data_inicial, MAX(p.date) AS data_final,
                       COUNT(p.rowid) AS total_registros
                FROM assets a LEFT JOIN asset_prices p ON p.asset_id = a.id
                GROUP BY a.id
                ORDER BY total_registros DESC
                LIMIT ? OFFSET ?
            """
            items = rows_to_dicts(conn.execute(sql, (safe_limit(limit), safe_offset(offset))).fetchall())
        else:
            items = rows_to_dicts(conn.execute(f"SELECT {ticker_expr} AS ticker, NULL AS data_inicial, NULL AS data_final, 0 AS total_registros FROM assets LIMIT ? OFFSET ?", (safe_limit(limit), safe_offset(offset))).fetchall())
        if table_exists(conn, "asset_dividends") and "asset_id" in div_cols:
            div_asset_ids = {r["asset_id"] for r in conn.execute("SELECT DISTINCT asset_id FROM asset_dividends WHERE asset_id IS NOT NULL").fetchall()}
            id_by_ticker = {}
            if "id" in asset_cols and "ticker" in asset_cols:
                id_by_ticker = {r["ticker"]: r["id"] for r in conn.execute("SELECT id, ticker FROM assets").fetchall()}
            for item in items:
                item["tem_dividendos"] = "sim" if id_by_ticker.get(item.get("ticker")) in div_asset_ids else "não"
        with_prices = sum(1 for i in items if (i.get("total_registros") or 0) > 0)
        return {"items": items, "summary": {"assets_with_prices_in_page": with_prices, "assets_without_prices_in_page": len(items) - with_prices}}

@router.get("/prices/{ticker}")
def prices(ticker: str, limit: int = Query(500, ge=1, le=5000), offset: int = Query(0, ge=0)) -> dict:
    with connect() as conn:
        if not table_exists(conn, "asset_prices"):
            return {"items": []}
        cols = columns(conn, "asset_prices")
        asset_id = asset_id_for_ticker(conn, ticker)
        selected = [c for c in ["date", "open", "high", "low", "close", "adjusted_close", "volume", "source"] if c in cols]
        if not selected:
            return {"items": []}
        if asset_id is not None and "asset_id" in cols:
            rows = conn.execute(f"SELECT {', '.join(selected)} FROM asset_prices WHERE asset_id=? ORDER BY date LIMIT ? OFFSET ?", (asset_id, safe_limit(limit, maximum=5000), safe_offset(offset))).fetchall()
        elif "ticker" in cols:
            rows = conn.execute(f"SELECT {', '.join(selected)} FROM asset_prices WHERE UPPER(ticker)=UPPER(?) ORDER BY date LIMIT ? OFFSET ?", (ticker, safe_limit(limit, maximum=5000), safe_offset(offset))).fetchall()
        else:
            rows = []
        return {"items": rows_to_dicts(rows)}

@router.get("/dividends/{ticker}")
def dividends(ticker: str, limit: int = Query(500, ge=1, le=5000)) -> dict:
    with connect() as conn:
        if not table_exists(conn, "asset_dividends"):
            return {"items": []}
        cols = columns(conn, "asset_dividends")
        selected = [c for c in ["payment_date", "ex_date", "date", "amount", "source", "created_at"] if c in cols]
        asset_id = asset_id_for_ticker(conn, ticker)
        if asset_id is not None and "asset_id" in cols:
            date_col = pick(cols, "payment_date", "ex_date", "date", default="rowid")
            rows = conn.execute(f"SELECT {', '.join(selected) if selected else '*'} FROM asset_dividends WHERE asset_id=? ORDER BY {date_col} LIMIT ?", (asset_id, safe_limit(limit, maximum=5000))).fetchall()
        elif "ticker" in cols:
            rows = conn.execute(f"SELECT {', '.join(selected) if selected else '*'} FROM asset_dividends WHERE UPPER(ticker)=UPPER(?) LIMIT ?", (ticker, safe_limit(limit, maximum=5000))).fetchall()
        else:
            rows = []
        return {"items": rows_to_dicts(rows)}

@router.get("/macro")
def macro(limit: int = Query(500, ge=1, le=5000)) -> dict:
    with connect() as conn:
        if not table_exists(conn, "macro_indicators"):
            return {"items": []}
        cols = columns(conn, "macro_indicators")
        order = pick(cols, "date", "created_at", default="rowid")
        rows = conn.execute(f"SELECT * FROM macro_indicators ORDER BY {order} DESC LIMIT ?", (safe_limit(limit, maximum=5000),)).fetchall()
        return {"items": rows_to_dicts(rows)}

@router.get("/indices")
def indices(limit: int = Query(500, ge=1, le=5000)) -> dict:
    with connect() as conn:
        if not table_exists(conn, "market_indices"):
            return {"items": []}
        cols = columns(conn, "market_indices")
        order = pick(cols, "date", "created_at", default="rowid")
        rows = conn.execute(f"SELECT * FROM market_indices ORDER BY {order} DESC LIMIT ?", (safe_limit(limit, maximum=5000),)).fetchall()
        return {"items": rows_to_dicts(rows)}

@router.get("/sync-logs")
def sync_logs(limit: int = Query(100, ge=1, le=1000)) -> dict:
    with connect() as conn:
        if not table_exists(conn, "data_sync_logs"):
            return {"items": []}
        cols = columns(conn, "data_sync_logs")
        order = pick(cols, "started_at", "created_at", "id", default="rowid")
        rows = conn.execute(f"SELECT * FROM data_sync_logs ORDER BY {order} DESC LIMIT ?", (safe_limit(limit),)).fetchall()
        return {"items": rows_to_dicts(rows)}
