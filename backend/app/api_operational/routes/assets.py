from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from backend.app.api_operational.cache import ttl_cache
from backend.app.api_operational.db import connect, rows_to_dicts, safe_limit, safe_offset, table_exists, columns, pick

router = APIRouter()

@router.get("")
@ttl_cache(ttl_seconds=60)
def list_assets(
    asset_class: str | None = None,
    country: str | None = None,
    exchange: str | None = None,
    currency: str | None = None,
    is_active: int | None = None,
    search: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    with connect() as conn:
        if not table_exists(conn, "assets"):
            return {"items": [], "limit": limit, "offset": offset, "total": 0}
        cols = columns(conn, "assets")
        selected = [c for c in ["id", "ticker", "name", "asset_class", "country", "exchange", "currency", "source", "is_active", "last_updated_at", "created_at", "updated_at"] if c in cols]
        sql = f"SELECT {', '.join(selected) if selected else '*'} FROM assets WHERE 1=1"
        params: list[object] = []
        filters = {"asset_class": asset_class, "country": country, "exchange": exchange, "currency": currency, "is_active": is_active}
        for col, value in filters.items():
            if value is not None and col in cols:
                sql += f" AND {col} = ?"
                params.append(value)
        if search and {"ticker", "name"} & cols:
            clauses = []
            if "ticker" in cols:
                clauses.append("ticker LIKE ?")
                params.append(f"%{search}%")
            if "name" in cols:
                clauses.append("name LIKE ?")
                params.append(f"%{search}%")
            sql += " AND (" + " OR ".join(clauses) + ")"
        total_sql = "SELECT COUNT(*) AS total FROM (" + sql + ") q"
        total = conn.execute(total_sql, params).fetchone()["total"]
        order_col = "ticker" if "ticker" in cols else selected[0] if selected else "rowid"
        sql += f" ORDER BY {order_col} LIMIT ? OFFSET ?"
        params.extend([safe_limit(limit), safe_offset(offset)])
        return {"items": rows_to_dicts(conn.execute(sql, params).fetchall()), "limit": limit, "offset": offset, "total": total}

@router.get("/classes")
@ttl_cache(ttl_seconds=60)
def asset_classes() -> dict:
    with connect() as conn:
        if not table_exists(conn, "assets") or "asset_class" not in columns(conn, "assets"):
            return {"items": []}
        rows = conn.execute("SELECT asset_class, COUNT(*) AS total FROM assets GROUP BY asset_class ORDER BY total DESC").fetchall()
        return {"items": rows_to_dicts(rows)}

@router.get("/summary")
@ttl_cache(ttl_seconds=60)
def assets_summary() -> dict:
    with connect() as conn:
        if not table_exists(conn, "assets"):
            return {"total": 0, "by_class": [], "by_country": []}
        cols = columns(conn, "assets")
        total = conn.execute("SELECT COUNT(*) AS total FROM assets").fetchone()["total"]
        by_class = rows_to_dicts(conn.execute("SELECT asset_class, COUNT(*) AS total FROM assets GROUP BY asset_class ORDER BY total DESC").fetchall()) if "asset_class" in cols else []
        by_country = rows_to_dicts(conn.execute("SELECT country, COUNT(*) AS total FROM assets GROUP BY country ORDER BY total DESC").fetchall()) if "country" in cols else []
        return {"total": total, "by_class": by_class, "by_country": by_country}

@router.get("/{ticker}")
def asset_detail(ticker: str) -> dict:
    with connect() as conn:
        if not table_exists(conn, "assets"):
            raise HTTPException(status_code=404, detail="Tabela assets não encontrada")
        cols = columns(conn, "assets")
        ticker_col = pick(cols, "ticker")
        if not ticker_col:
            raise HTTPException(status_code=404, detail="Coluna ticker não encontrada")
        row = conn.execute("SELECT * FROM assets WHERE UPPER(ticker)=UPPER(?) LIMIT 1", (ticker,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Ativo não encontrado")
        return dict(row)
