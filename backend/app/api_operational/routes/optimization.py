from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from backend.app.api_operational.db import connect, rows_to_dicts, safe_limit, table_exists, columns, pick

router = APIRouter()

@router.get("/runs")
def runs(limit: int = Query(100, ge=1, le=1000)) -> dict:
    with connect() as conn:
        if not table_exists(conn, "optimization_runs"):
            return {"items": []}
        cols = columns(conn, "optimization_runs")
        order = pick(cols, "created_at", "id", default="rowid")
        rows = conn.execute(f"SELECT * FROM optimization_runs ORDER BY {order} DESC LIMIT ?", (safe_limit(limit),)).fetchall()
        return {"items": rows_to_dicts(rows)}

@router.get("/runs/{run_id}")
def run_detail(run_id: int) -> dict:
    with connect() as conn:
        if not table_exists(conn, "optimization_runs"):
            raise HTTPException(status_code=404, detail="Tabela optimization_runs não encontrada")
        row = conn.execute("SELECT * FROM optimization_runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Run não encontrada")
        return dict(row)

@router.get("/results")
def results(run_id: int | None = None, limit: int = Query(100, ge=1, le=1000)) -> dict:
    with connect() as conn:
        if not table_exists(conn, "optimization_results"):
            return {"items": []}
        cols = columns(conn, "optimization_results")
        sql = "SELECT * FROM optimization_results WHERE 1=1"
        params: list[object] = []
        if run_id is not None and "run_id" in cols:
            sql += " AND run_id=?"
            params.append(run_id)
        order = pick(cols, "score_robustez", "sharpe_ratio", "total_return", "id", default="rowid")
        sql += f" ORDER BY {order} DESC LIMIT ?"
        params.append(safe_limit(limit))
        rows = conn.execute(sql, params).fetchall()
        return {"items": rows_to_dicts(rows)}

@router.get("/best")
def best(limit: int = Query(20, ge=1, le=200)) -> dict:
    return results(run_id=None, limit=limit)
