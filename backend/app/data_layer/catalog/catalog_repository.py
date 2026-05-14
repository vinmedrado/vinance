from __future__ import annotations

from db import pg_compat as dbcompat
from typing import Iterable

from backend.app.data_layer.catalog.catalog_classifier import classify_asset, normalize_ticker
from backend.app.data_layer.repositories.sqlite_repository import add_column_if_missing, connect, ensure_patch6_schema, now_iso


def ensure_catalog_schema(conn: dbcompat.Connection) -> None:
    ensure_patch6_schema(conn)
    add_column_if_missing(conn, "assets", "exchange", "VARCHAR(32)")
    add_column_if_missing(conn, "assets", "is_active", "INTEGER DEFAULT 1 NOT NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_assets_asset_class ON assets(asset_class)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_assets_country ON assets(country)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_assets_is_active ON assets(is_active)")


def upsert_catalog_asset(conn: dbcompat.Connection, item: dict, dry_run: bool = False) -> tuple[int | None, bool]:
    ensure_catalog_schema(conn)
    now = now_iso()
    ticker = normalize_ticker(item.get("ticker"))
    asset_class = classify_asset(ticker, item.get("name"), item.get("asset_class"))
    # Prefer an existing row already using the canonical class. If only a legacy
    # class exists (ex: ACAO/CRIPTO), update that row. This avoids creating or
    # triggering duplicates after PATCH 7 normalizes classes to english names.
    existing = conn.execute(
        """
        SELECT id, asset_class
          FROM assets
         WHERE UPPER(ticker) = ?
         ORDER BY CASE WHEN LOWER(asset_class) = ? THEN 0 ELSE 1 END, id
         LIMIT 1
        """,
        (ticker, asset_class),
    ).fetchone()
    values = {
        "symbol": item.get("symbol") or ticker,
        "ticker": ticker,
        "name": item.get("name") or ticker,
        "asset_class": asset_class,
        "currency": item.get("currency") or "BRL",
        "source": item.get("source") or "catalog",
        "country": item.get("country") or "BR",
        "exchange": item.get("exchange") or "",
        "is_active": int(bool(item.get("is_active", True))),
        "last_updated_at": now,
        "created_at": now,
        "updated_at": now,
    }
    if existing:
        if not dry_run:
            try:
                conn.execute(
                    """
                    UPDATE assets
                       SET symbol = ?, name = ?, asset_class = ?, currency = ?, source = ?, country = ?,
                           exchange = ?, is_active = ?, last_updated_at = ?, updated_at = ?
                     WHERE id = ?
                    """,
                    (values["symbol"], values["name"], values["asset_class"], values["currency"], values["source"],
                     values["country"], values["exchange"], values["is_active"], values["last_updated_at"], values["updated_at"], existing["id"]),
                )
            except dbcompat.IntegrityError:
                canonical = conn.execute(
                    "SELECT id FROM assets WHERE UPPER(ticker) = ? AND LOWER(asset_class) = ? LIMIT 1",
                    (ticker, asset_class),
                ).fetchone()
                if canonical:
                    conn.execute(
                        """
                        UPDATE assets
                           SET symbol = ?, name = ?, currency = ?, source = ?, country = ?,
                               exchange = ?, is_active = ?, last_updated_at = ?, updated_at = ?
                         WHERE id = ?
                        """,
                        (values["symbol"], values["name"], values["currency"], values["source"], values["country"],
                         values["exchange"], values["is_active"], values["last_updated_at"], values["updated_at"], canonical["id"]),
                    )
                    return int(canonical["id"]), False
                raise
        return int(existing["id"]), False
    if dry_run:
        return None, True
    cur = conn.execute(
        """
        INSERT INTO assets
        (symbol, ticker, name, asset_class, currency, source, country, exchange, is_active, last_updated_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (values["symbol"], values["ticker"], values["name"], values["asset_class"], values["currency"], values["source"],
         values["country"], values["exchange"], values["is_active"], values["last_updated_at"], values["created_at"], values["updated_at"]),
    )
    return int(cur.lastrowid), True


def upsert_many(items: Iterable[dict], dry_run: bool = False) -> dict:
    inserted = updated = skipped = 0
    with connect() as conn:
        ensure_catalog_schema(conn)
        for item in items:
            if not item.get("ticker"):
                skipped += 1
                continue
            _, was_inserted = upsert_catalog_asset(conn, item, dry_run=dry_run)
            if was_inserted:
                inserted += 1
            else:
                updated += 1
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


def fetch_catalog_assets() -> list[dict]:
    with connect() as conn:
        ensure_catalog_schema(conn)
        rows = conn.execute("SELECT ticker, name, asset_class, country, currency, exchange, is_active FROM assets ORDER BY asset_class, ticker").fetchall()
        return [dict(row) for row in rows]
