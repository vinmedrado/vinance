from __future__ import annotations

from db import pg_compat as dbcompat
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[4]
CORE_ROOT_DIR = BASE_DIR / "data" / "POSTGRES_RUNTIME_DISABLED"


def _connect() -> dbcompat.Connection:
    conn = dbcompat.connect(CORE_ROOT_DIR)
    conn.row_factory = dbcompat.Row
    return conn


def _table_exists(conn: dbcompat.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def get_core_summary() -> dict[str, Any]:
    """Lê o SQLite original sem mexer no schema.

    Mantém o módulo core independente do backend SQLAlchemy dos módulos novos.
    """
    summary: dict[str, Any] = {
        "database": str(CORE_ROOT_DIR),
        "despesas_total": 0.0,
        "despesas_pendentes": 0.0,
        "despesas_pagas": 0.0,
        "receitas_total": 0.0,
        "saldo_estimado": 0.0,
        "renda_mensal_estimada": None,
        "gasto_mensal_estimado": 0.0,
        "tables_found": [],
    }
    if not CORE_ROOT_DIR.exists():
        return summary

    with _connect() as conn:
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        summary["tables_found"] = tables

        if _table_exists(conn, "despesas"):
            rows = conn.execute("SELECT valor_parcela, valor_a_pagar, valor_total, situacao, status FROM despesas").fetchall()
            total = 0.0
            pending = 0.0
            paid = 0.0
            for row in rows:
                valor = row["valor_a_pagar"] if row["valor_a_pagar"] is not None else row["valor_parcela"] or row["valor_total"] or 0
                valor = float(valor or 0)
                total += valor
                situacao = (row["situacao"] or row["status"] or "").lower()
                if "pago" in situacao:
                    paid += valor
                else:
                    pending += valor
            summary["despesas_total"] = round(total, 2)
            summary["despesas_pendentes"] = round(pending, 2)
            summary["despesas_pagas"] = round(paid, 2)
            summary["gasto_mensal_estimado"] = round(pending, 2)

        if _table_exists(conn, "receitas"):
            cols = [row[1] for row in conn.execute("PRAGMA table_info(receitas)").fetchall()]
            value_col = "valor" if "valor" in cols else "valor_total" if "valor_total" in cols else None
            if value_col:
                receita = float(conn.execute(f"SELECT COALESCE(SUM({value_col}), 0) FROM receitas").fetchone()[0] or 0)
                summary["receitas_total"] = round(receita, 2)
                summary["renda_mensal_estimada"] = round(receita, 2)

    summary["saldo_estimado"] = round(summary["receitas_total"] - summary["despesas_pendentes"], 2)
    return summary
