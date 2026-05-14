
from __future__ import annotations

from typing import Any
from sqlalchemy import text

from services.db_session import db_session


def ensure_asset_catalog_table() -> None:
    with db_session() as db:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS asset_catalog (
                id SERIAL PRIMARY KEY,
                tenant_id UUID,
                ticker TEXT NOT NULL,
                name TEXT,
                asset_class TEXT,
                exchange TEXT,
                currency TEXT,
                data_quality_score REAL DEFAULT 50,
                reliability_status TEXT DEFAULT 'unknown',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_asset_catalog_tenant ON asset_catalog(tenant_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_asset_catalog_ticker ON asset_catalog(ticker)"))
        db.commit()


def upsert_asset(asset: dict[str, Any], tenant_id: str) -> None:
    ensure_asset_catalog_table()
    with db_session() as db:
        db.execute(
            text("""
                INSERT INTO asset_catalog
                (tenant_id, ticker, name, asset_class, exchange, currency, data_quality_score, reliability_status, updated_at)
                VALUES (:tenant_id, :ticker, :name, :asset_class, :exchange, :currency, :data_quality_score, :reliability_status, NOW())
                ON CONFLICT DO NOTHING
            """),
            {
                "tenant_id": tenant_id,
                "ticker": asset.get("ticker"),
                "name": asset.get("name"),
                "asset_class": asset.get("asset_class"),
                "exchange": asset.get("exchange"),
                "currency": asset.get("currency"),
                "data_quality_score": asset.get("data_quality_score", 50),
                "reliability_status": asset.get("reliability_status", "unknown"),
            },
        )
        db.commit()


def list_assets(tenant_id: str, limit: int = 1000) -> list[dict[str, Any]]:
    ensure_asset_catalog_table()
    with db_session() as db:
        rows = db.execute(
            text("""
                SELECT *
                FROM asset_catalog
                WHERE tenant_id=:tenant_id
                ORDER BY ticker
                LIMIT :limit
            """),
            {"tenant_id": tenant_id, "limit": int(limit)},
        ).mappings().all()
        return [dict(r) for r in rows]


def get_asset(ticker: str, tenant_id: str) -> dict[str, Any] | None:
    ensure_asset_catalog_table()
    with db_session() as db:
        row = db.execute(
            text("""
                SELECT *
                FROM asset_catalog
                WHERE tenant_id=:tenant_id AND ticker=:ticker
                LIMIT 1
            """),
            {"tenant_id": tenant_id, "ticker": ticker},
        ).mappings().first()
        return dict(row) if row else None
