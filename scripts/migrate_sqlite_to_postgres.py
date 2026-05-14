
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3

from sqlalchemy import text
from db.database import SessionLocal

DEFAULT_SQLITE_PATH = Path("data/financas.db")


def migrate_table(sqlite_conn, pg_db, table: str, tenant_id: str | None = None, dry_run: bool = True) -> dict:
    exists = sqlite_conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not exists:
        return {"table": table, "status": "missing_sqlite_table", "rows": 0}

    rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
    cols = [d[0] for d in sqlite_conn.execute(f"SELECT * FROM {table} LIMIT 1").description or []]
    if dry_run:
        return {"table": table, "status": "dry_run", "rows": len(rows), "columns": cols}

    migrated = 0
    for row in rows:
        data = dict(zip(cols, row))
        if tenant_id and "tenant_id" not in data:
            data["tenant_id"] = tenant_id
        columns = list(data.keys())
        placeholders = [f":{c}" for c in columns]
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)}) ON CONFLICT DO NOTHING"
        pg_db.execute(text(sql), data)
        migrated += 1
    return {"table": table, "status": "migrated", "rows": migrated}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--tenant-id", default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--tables", nargs="*", default=["asset_catalog", "asset_prices", "ml_predictions", "portfolio_accounts", "portfolio_transactions"])
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite_path)
    if not sqlite_path.exists():
        print({"status": "missing_sqlite_file", "path": str(sqlite_path)})
        return 1

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    dry_run = not args.execute

    with SessionLocal() as pg_db:
        results = []
        for table in args.tables:
            results.append(migrate_table(sqlite_conn, pg_db, table, tenant_id=args.tenant_id, dry_run=dry_run))
        if dry_run:
            pg_db.rollback()
        else:
            pg_db.commit()

    for result in results:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
