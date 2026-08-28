from __future__ import annotations

import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def _normalize_url(url: str) -> str:
    replacements = {
        "postgres://": "postgresql+psycopg2://",
        "postgresql+asyncpg://": "postgresql+psycopg2://",
        "postgresql+psycopg://": "postgresql+psycopg2://",
    }
    for prefix, replacement in replacements.items():
        if url.startswith(prefix):
            url = replacement + url[len(prefix):]
            break

    parts = urlsplit(url)
    unsupported = {"connect_timeout", "command_timeout"}
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in unsupported]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def create_sync_engine(database_url: str | None = None) -> Engine:
    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL não encontrada.")
    return create_engine(_normalize_url(url), pool_pre_ping=True, pool_recycle=300)
