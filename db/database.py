from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

ENV = os.getenv("FINANCEOS_ENV", "development").lower()
DATABASE_URL = os.getenv("DATABASE_URL")

if ENV == "production" and not DATABASE_URL:
    raise RuntimeError("DATABASE_URL obrigatório em produção.")

if not DATABASE_URL:
    DATABASE_URL = "postgresql+asyncpg://financeos:financeos@localhost:5432/financeos"

if ENV == "production" and "sqlite" in DATABASE_URL.lower():
    raise RuntimeError("SQLite não permitido em produção.")

SYNC_DATABASE_URL = os.getenv("SYNC_DATABASE_URL") or DATABASE_URL.replace("+asyncpg", "+psycopg2")
if ENV == "production" and "sqlite" in SYNC_DATABASE_URL.lower():
    raise RuntimeError("SQLite não permitido em produção.")

async_engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, future=True)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
sync_engine = create_engine(SYNC_DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=sync_engine, autoflush=False, autocommit=False)

async def get_async_session():
    async with AsyncSessionLocal() as session:
        yield session

def get_sync_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_connection():
    """Compatibilidade para páginas antigas.

    Produção usa SQLAlchemy/PostgreSQL. Para legado Streamlit com consultas sqlite-style,
    habilite explicitamente FINANCEOS_LOCAL_SQLITE=true. O arquivo local não deve ser versionado.
    """
    if ENV == "production":
        raise RuntimeError("get_connection legado bloqueado em produção. Use SessionLocal/SQLAlchemy.")
    if os.getenv("FINANCEOS_LOCAL_SQLITE", "false").lower() == "true":
        db_path = Path(os.getenv("FINANCEOS_SQLITE_PATH", "data/local_dev.sqlite3"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(db_path)
    raise RuntimeError("Conexão legada desativada. Use PostgreSQL/SessionLocal ou defina FINANCEOS_LOCAL_SQLITE=true apenas para desenvolvimento local.")
