
from __future__ import annotations

from db.database import SessionLocal
from sqlalchemy import text


def get_conn():
    return SessionLocal()


def execute(sql: str, params: dict | None = None):
    db = SessionLocal()
    try:
        result = db.execute(text(sql), params or {})
        db.commit()
        return result
    finally:
        db.close()
