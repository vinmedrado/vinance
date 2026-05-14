from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from backend.app.api_operational.cache import ttl_cache
from backend.app.api_operational.db import connect, rows_to_dicts, safe_limit, safe_offset, table_exists, columns, pick

router = APIRouter()

@router.get("/scores")
@ttl_cache(ttl_seconds=60)
def scores(asset_class: str | None = None, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)) -> dict:
    with connect() as conn:
        if not table_exists(conn, "asset_scores"):
            return {"items": []}
        cols = columns(conn, "asset_scores")
        sql = "SELECT * FROM asset_scores WHERE 1=1"
        params = []
        if asset_class and "asset_class" in cols:
            sql += " AND asset_class=?"
            params.append(asset_class)
        order = pick(cols, "score_total", "calculated_at", "id", default="rowid")
        direction = "DESC" if order in {"score_total", "calculated_at", "id"} else "ASC"
        sql += f" ORDER BY {order} {direction} LIMIT ? OFFSET ?"
        params.extend([safe_limit(limit), safe_offset(offset)])
        return {"items": rows_to_dicts(conn.execute(sql, params).fetchall())}

@router.get("/scores/{ticker}")
def score_detail(ticker: str) -> dict:
    with connect() as conn:
        if not table_exists(conn, "asset_scores"):
            raise HTTPException(status_code=404, detail="Tabela asset_scores não encontrada")
        cols = columns(conn, "asset_scores")
        if "ticker" in cols:
            row = conn.execute("SELECT * FROM asset_scores WHERE UPPER(ticker)=UPPER(?) ORDER BY calculated_at DESC LIMIT 1", (ticker,)).fetchone()
        else:
            row = None
        if row is None:
            raise HTTPException(status_code=404, detail="Score não encontrado")
        return dict(row)

@router.get("/rankings")
@ttl_cache(ttl_seconds=60)
def rankings(asset_class: str | None = None, limit: int = Query(100, ge=1, le=1000)) -> dict:
    table = "asset_rankings" if True else "asset_scores"
    with connect() as conn:
        if table_exists(conn, "asset_rankings"):
            cols = columns(conn, "asset_rankings")
            sql = "SELECT * FROM asset_rankings WHERE 1=1"
            params = []
            if asset_class and "asset_class" in cols:
                sql += " AND asset_class=?"
                params.append(asset_class)
            order = pick(cols, "rank_position", "score_total", "id", default="rowid")
            sql += f" ORDER BY {order} {'ASC' if order == 'rank_position' else 'DESC'} LIMIT ?"
            params.append(safe_limit(limit))
            return {"items": rows_to_dicts(conn.execute(sql, params).fetchall())}
        return scores(asset_class=asset_class, limit=limit, offset=0)

@router.get("/metrics/{ticker}")
def metrics(ticker: str) -> dict:
    with connect() as conn:
        if not table_exists(conn, "asset_analysis_metrics"):
            return {"items": []}
        cols = columns(conn, "asset_analysis_metrics")
        if "ticker" in cols:
            rows = conn.execute("SELECT * FROM asset_analysis_metrics WHERE UPPER(ticker)=UPPER(?) ORDER BY calculated_at DESC LIMIT 20", (ticker,)).fetchall()
        elif "asset_id" in cols and table_exists(conn, "assets"):
            asset = conn.execute("SELECT id FROM assets WHERE UPPER(ticker)=UPPER(?) LIMIT 1", (ticker,)).fetchone()
            rows = conn.execute("SELECT * FROM asset_analysis_metrics WHERE asset_id=? LIMIT 20", (asset["id"],)).fetchall() if asset else []
        else:
            rows = []
        return {"items": rows_to_dicts(rows)}

@router.get("/summary")
@ttl_cache(ttl_seconds=60)
def analysis_summary() -> dict:
    with connect() as conn:
        score_total = conn.execute("SELECT COUNT(*) AS total FROM asset_scores").fetchone()["total"] if table_exists(conn, "asset_scores") else 0
        ranking_total = conn.execute("SELECT COUNT(*) AS total FROM asset_rankings").fetchone()["total"] if table_exists(conn, "asset_rankings") else 0
        by_class = []
        if table_exists(conn, "asset_scores") and "asset_class" in columns(conn, "asset_scores"):
            by_class = rows_to_dicts(conn.execute("SELECT asset_class, COUNT(*) AS total, AVG(score_total) AS avg_score FROM asset_scores GROUP BY asset_class ORDER BY total DESC").fetchall())
        return {"scores": score_total, "rankings": ranking_total, "by_class": by_class}
