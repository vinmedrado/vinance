from __future__ import annotations

from sqlalchemy import text
from db.database import SessionLocal


class PostgresRepository:
    def fetch_all(self, sql: str, params: dict | None = None):
        with SessionLocal() as db:
            return [dict(r) for r in db.execute(text(sql), params or {}).mappings().all()]

    def fetch_one(self, sql: str, params: dict | None = None):
        with SessionLocal() as db:
            row = db.execute(text(sql), params or {}).mappings().first()
            return dict(row) if row else None

    def execute(self, sql: str, params: dict | None = None):
        with SessionLocal() as db:
            result = db.execute(text(sql), params or {})
            db.commit()
            return result


def connect():
    return SessionLocal()


def ensure_patch6_schema(*args, **kwargs):
    return None


def start_log(*args, **kwargs):
    return None


def finish_log(*args, **kwargs):
    return None


def upsert_asset(*args, **kwargs):
    return None


def fetch_assets(*args, **kwargs):
    return []


def insert_dividend_rows(*args, **kwargs):
    return 0


def write_sync_log(*args, **kwargs):
    return None

def insert_price_rows(*args, **kwargs):
    return 0


def upsert_price_rows(*args, **kwargs):
    return 0


def fetch_price_rows(*args, **kwargs):
    return []


def fetch_dividend_rows(*args, **kwargs):
    return []

def get_last_price_date(*args, **kwargs):
    return None

def get_last_index_date(*args, **kwargs):
    return None


def insert_index_rows(*args, **kwargs):
    return 0

def insert_macro_rows(*args, **kwargs):
    return 0

LegacyRepository = PostgresRepository
SQLiteRepository = PostgresRepository