
from __future__ import annotations

from sqlalchemy import text
from db.database import SessionLocal


class PgCompatConnection:
    def __init__(self):
        self.db = SessionLocal()

    def execute(self, sql, params=None):
        return self.db.execute(text(str(sql)), params or {})

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()

    def close(self):
        self.db.close()


def connect(*args, **kwargs):
    return PgCompatConnection()
