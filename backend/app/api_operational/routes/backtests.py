from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from backend.app.api_operational.db import connect, rows_to_dicts, safe_limit, table_exists, columns, pick

router = APIRouter()

@router.get("")
def list_backtests(limit: int = Query(100, ge=1, le=1000)) -> dict:
    with connect() as conn:
        if not table_exists(conn, "backtest_runs"):
            return {"items": []}
        cols = columns(conn, "backtest_runs")
        order = pick(cols, "created_at", "id", default="rowid")
        rows = conn.execute(f"SELECT * FROM backtest_runs ORDER BY {order} DESC LIMIT ?", (safe_limit(limit),)).fetchall()
        return {"items": rows_to_dicts(rows)}

@router.get("/{backtest_id}")
def backtest_detail(backtest_id: int) -> dict:
    with connect() as conn:
        if not table_exists(conn, "backtest_runs"):
            raise HTTPException(status_code=404, detail="Tabela backtest_runs não encontrada")
        row = conn.execute("SELECT * FROM backtest_runs WHERE id=?", (backtest_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Backtest não encontrado")
        return dict(row)

@router.get("/{backtest_id}/trades")
def trades(backtest_id: int, limit: int = Query(1000, ge=1, le=5000)) -> dict:
    with connect() as conn:
        if not table_exists(conn, "backtest_trades"):
            return {"items": []}
        cols = columns(conn, "backtest_trades")
        order = pick(cols, "date", "id", default="rowid")
        rows = conn.execute(f"SELECT * FROM backtest_trades WHERE backtest_id=? ORDER BY {order} LIMIT ?", (backtest_id, safe_limit(limit, maximum=5000))).fetchall()
        return {"items": rows_to_dicts(rows)}

@router.get("/{backtest_id}/equity-curve")
def equity_curve(backtest_id: int, limit: int = Query(5000, ge=1, le=10000)) -> dict:
    with connect() as conn:
        if not table_exists(conn, "backtest_equity_curve"):
            return {"items": []}
        cols = columns(conn, "backtest_equity_curve")
        order = pick(cols, "date", "id", default="rowid")
        rows = conn.execute(f"SELECT * FROM backtest_equity_curve WHERE backtest_id=? ORDER BY {order} LIMIT ?", (backtest_id, safe_limit(limit, maximum=10000))).fetchall()
        return {"items": rows_to_dicts(rows)}

@router.get("/{backtest_id}/metrics")
def metrics(backtest_id: int) -> dict:
    with connect() as conn:
        if not table_exists(conn, "backtest_metrics"):
            return {"items": []}
        rows = conn.execute("SELECT * FROM backtest_metrics WHERE backtest_id=?", (backtest_id,)).fetchall()
        return {"items": rows_to_dicts(rows)}
