from db.database import SessionLocal
from sqlalchemy import text


def connect():
    return SessionLocal()


def table_exists(table_name: str) -> bool:
    try:
        with SessionLocal() as db:
            db.execute(text(f"SELECT 1 FROM {table_name} LIMIT 1"))
            return True
    except Exception:
        return False

def rows_to_dicts(rows):
    return [dict(r) for r in rows]


def safe_limit(limit, default=100, max_value=1000):
    try:
        limit = int(limit)
        return min(limit, max_value)
    except Exception:
        return default


def safe_offset(offset):
    try:
        return max(int(offset), 0)
    except Exception:
        return 0


def columns(*args, **kwargs):
    return []


def pick(data, *keys):
    if not isinstance(data, dict):
        return {}
    return {k: data.get(k) for k in keys}
