
from __future__ import annotations

from typing import Any
from sqlalchemy import text

from db.database import SessionLocal


def _session():
    return SessionLocal()


def get_default_account(tenant_id: str, user_id: str = "system") -> str | int:
    with _session() as db:
        row = db.execute(
            text("SELECT id FROM portfolio_accounts WHERE tenant_id=:tenant_id ORDER BY created_at ASC LIMIT 1"),
            {"tenant_id": tenant_id},
        ).mappings().first()
        if row:
            return row["id"]

        row = db.execute(
            text("""
                INSERT INTO portfolio_accounts (tenant_id, user_id, name, broker, currency)
                VALUES (:tenant_id, :user_id, 'Carteira Principal', NULL, 'BRL')
                RETURNING id
            """),
            {"tenant_id": tenant_id, "user_id": user_id},
        ).mappings().first()
        db.commit()
        return row["id"]


def _latest_prices(db, tenant_id: str) -> dict[str, float]:
    try:
        rows = db.execute(
            text("""
                SELECT DISTINCT ON (ticker) ticker, COALESCE(close, adjusted_close, adj_close, price, close_price) AS price
                FROM asset_prices
                WHERE tenant_id=:tenant_id
                ORDER BY ticker, COALESCE(date, price_date, created_at) DESC
            """),
            {"tenant_id": tenant_id},
        ).mappings().all()
        return {str(r["ticker"]): float(r["price"] or 0) for r in rows}
    except Exception:
        return {}


def get_positions(account_id: str | int, tenant_id: str) -> list[dict[str, Any]]:
    with _session() as db:
        rows = db.execute(
            text("""
                SELECT *
                FROM portfolio_transactions
                WHERE account_id=:account_id AND tenant_id=:tenant_id
                ORDER BY transaction_date ASC, id ASC
            """),
            {"account_id": account_id, "tenant_id": tenant_id},
        ).mappings().all()
        prices = _latest_prices(db, tenant_id)

    positions: dict[str, dict[str, Any]] = {}
    for r in rows:
        ticker = str(r["ticker"])
        positions.setdefault(ticker, {"ticker": ticker, "quantity": 0.0, "cost": 0.0, "dividends": 0.0})
        qty = float(r["quantity"] or 0)
        total = float(r["total_value"] or 0) + float(r.get("fees") or 0)
        ttype = str(r["transaction_type"]).upper()
        if ttype == "BUY":
            positions[ticker]["quantity"] += qty
            positions[ticker]["cost"] += total
        elif ttype == "SELL":
            avg = positions[ticker]["cost"] / positions[ticker]["quantity"] if positions[ticker]["quantity"] else 0
            positions[ticker]["quantity"] -= qty
            positions[ticker]["cost"] -= avg * qty
        elif ttype == "DIVIDEND":
            positions[ticker]["dividends"] += total

    out = []
    for ticker, p in positions.items():
        qty = p["quantity"]
        if abs(qty) < 1e-9:
            continue
        avg_price = p["cost"] / qty if qty else 0
        current_price = prices.get(ticker, avg_price)
        current_value = qty * current_price
        pnl = current_value - p["cost"]
        pnl_pct = pnl / p["cost"] if p["cost"] else 0
        out.append({
            "ticker": ticker,
            "quantity": qty,
            "avg_price": avg_price,
            "current_price": current_price,
            "current_value": current_value,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "dividends": p["dividends"],
        })
    return out


def get_portfolio_summary(tenant_id: str, user_id: str = "system") -> dict[str, Any]:
    account_id = get_default_account(tenant_id, user_id)
    positions = get_positions(account_id, tenant_id)
    total = sum(float(p["current_value"]) for p in positions)
    total_cost = sum(float(p["avg_price"]) * float(p["quantity"]) for p in positions)
    pnl = total - total_cost
    return {
        "account_id": account_id,
        "total_brl": total,
        "positions_count": len(positions),
        "pnl": pnl,
        "pnl_pct": pnl / total_cost if total_cost else 0,
        "return_mtd": None,
        "return_ytd": None,
        "positions": positions,
    }


def get_dividends_received(account_id: str | int, tenant_id: str, year: int | None = None) -> float:
    sql = """
        SELECT COALESCE(SUM(total_value), 0) AS total
        FROM portfolio_transactions
        WHERE account_id=:account_id AND tenant_id=:tenant_id AND UPPER(transaction_type)='DIVIDEND'
    """
    params = {"account_id": account_id, "tenant_id": tenant_id}
    if year:
        sql += " AND EXTRACT(YEAR FROM transaction_date)=:year"
        params["year"] = year
    with _session() as db:
        row = db.execute(text(sql), params).mappings().first()
        return float(row["total"] or 0) if row else 0.0


def calculate_pnl(transactions: list[dict[str, Any]], current_prices: dict[str, float]) -> dict[str, Any]:
    return {"summary": "Use get_positions(account_id, tenant_id) para cálculo consolidado.", "current_prices": current_prices}


def import_from_b3_excel(file, account_id: str | int, tenant_id: str) -> dict[str, Any]:
    import pandas as pd
    df = pd.read_excel(file)
    required = {"ticker", "transaction_type", "quantity", "price", "transaction_date"}
    normalized = {c.lower().strip(): c for c in df.columns}
    if not required.issubset(set(normalized.keys())):
        return {"imported": 0, "error": "Arquivo precisa conter ticker, transaction_type, quantity, price, transaction_date."}

    with _session() as db:
        imported = 0
        for _, row in df.iterrows():
            ticker = row[normalized["ticker"]]
            ttype = row[normalized["transaction_type"]]
            qty = float(row[normalized["quantity"]])
            price = float(row[normalized["price"]])
            total = qty * price
            date = str(row[normalized["transaction_date"]])[:10]
            db.execute(
                text("""
                    INSERT INTO portfolio_transactions
                    (account_id, tenant_id, ticker, transaction_type, quantity, price, total_value, transaction_date)
                    VALUES (:account_id, :tenant_id, :ticker, :transaction_type, :quantity, :price, :total_value, :transaction_date)
                """),
                {
                    "account_id": account_id,
                    "tenant_id": tenant_id,
                    "ticker": ticker,
                    "transaction_type": ttype,
                    "quantity": qty,
                    "price": price,
                    "total_value": total,
                    "transaction_date": date,
                },
            )
            imported += 1
        db.commit()
    return {"imported": imported}
