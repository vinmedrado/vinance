from __future__ import annotations

from collections.abc import Iterable
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from db.database import sync_engine


def _convert_qmark(sql: str, params):
    if not isinstance(params, (list, tuple)):
        return sql, params or {}
    converted = []
    out = []
    idx = 0
    for char in sql:
        if char == "?":
            key = f"p{idx}"
            out.append(f":{key}")
            converted.append((key, params[idx]))
            idx += 1
        else:
            out.append(char)
    return "".join(out), dict(converted)


class OperationalConnection:
    def __init__(self):
        self._conn: Connection | None = None

    def __enter__(self):
        self._conn = sync_engine.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._conn is not None:
            if exc_type is None:
                try:
                    self._conn.commit()
                except Exception:
                    pass
            else:
                try:
                    self._conn.rollback()
                except Exception:
                    pass
            self._conn.close()

    def execute(self, sql, params=None):
        if self._conn is None:
            raise RuntimeError("OperationalConnection não inicializada")
        if isinstance(sql, str):
            sql, params = _convert_qmark(sql, params)
            return self._conn.execute(text(sql), params or {})
        return self._conn.execute(sql, params or {})


def connect():
    return OperationalConnection()


def _conn_from_args(args):
    if len(args) >= 2:
        return args[0], args[1]
    return None, args[0] if args else None


def table_exists(*args) -> bool:
    conn, table_name = _conn_from_args(args)
    if not table_name:
        return False
    try:
        if conn is not None and getattr(conn, "_conn", None) is not None:
            return inspect(conn._conn).has_table(str(table_name))
        with sync_engine.connect() as c:
            return inspect(c).has_table(str(table_name))
    except Exception:
        return False


def columns(*args, **kwargs):
    conn, table_name = _conn_from_args(args)
    if not table_name:
        return []
    try:
        if conn is not None and getattr(conn, "_conn", None) is not None:
            return [c["name"] for c in inspect(conn._conn).get_columns(str(table_name))]
        with sync_engine.connect() as c:
            return [c["name"] for c in inspect(c).get_columns(str(table_name))]
    except Exception:
        return []


def rows_to_dicts(rows):
    items = []
    for row in rows or []:
        if hasattr(row, "_mapping"):
            items.append(dict(row._mapping))
        elif isinstance(row, dict):
            items.append(dict(row))
        else:
            try:
                items.append(dict(row))
            except Exception:
                items.append({})
    return items


def safe_limit(limit, default=100, max_value=1000, maximum=None):
    ceiling = maximum if maximum is not None else max_value
    try:
        value = int(limit)
        return max(1, min(value, ceiling))
    except Exception:
        return default


def safe_offset(offset):
    try:
        return max(int(offset), 0)
    except Exception:
        return 0


def pick(data, *keys, default=None):
    values = set(data or []) if not isinstance(data, dict) else set(data.keys())
    for key in keys:
        if key in values:
            return key
    return default
