
from __future__ import annotations

from pathlib import Path
from sqlalchemy import text

from services.db_session import db_session

ROOT_DIR = Path(__file__).resolve().parents[1]


def execute_query(sql: str, params: dict | None = None):
    with db_session() as db:
        return db.execute(text(sql), params or {})


def fetch_all(sql: str, params: dict | None = None) -> list[dict]:
    with db_session() as db:
        rows = db.execute(text(sql), params or {}).mappings().all()
        return [dict(r) for r in rows]


def fetch_one(sql: str, params: dict | None = None) -> dict | None:
    with db_session() as db:
        row = db.execute(text(sql), params or {}).mappings().first()
        return dict(row) if row else None


def commit_sql(sql: str, params: dict | None = None):
    with db_session() as db:
        result = db.execute(text(sql), params or {})
        db.commit()
        return result


def table_exists(table_name: str) -> bool:
    with db_session() as db:
        row = db.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema='public' AND table_name=:table_name
                ) AS exists
            """),
            {"table_name": table_name},
        ).mappings().first()
        return bool(row["exists"]) if row else False


def get_table_count(table_name: str, tenant_id: str | None = None) -> int:
    if tenant_id:
        sql = f"SELECT COUNT(*) AS total FROM {table_name} WHERE tenant_id=:tenant_id"
        params = {"tenant_id": tenant_id}
    else:
        sql = f"SELECT COUNT(*) AS total FROM {table_name}"
        params = {}
    row = fetch_one(sql, params)
    return int(row["total"] or 0) if row else 0
