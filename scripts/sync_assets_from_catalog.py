from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.asset_catalog_db import connect, ensure_asset_catalog_schema, ensure_assets_schema_minimum, fetch_catalog, now_iso


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincroniza assets principais a partir do asset_catalog ativo.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--asset-class", default=None)
    args = parser.parse_args()

    stats = {"processed": 0, "inserted": 0, "updated": 0, "ignored": 0, "errors": 0}
    with connect() as conn:
        ensure_asset_catalog_schema(conn)
        ensure_assets_schema_minimum(conn)
        rows = fetch_catalog(conn, asset_class=args.asset_class, status="active", limit=args.limit)
        for row in rows:
            stats["processed"] += 1
            try:
                ticker = row["ticker"]
                asset_class = row["asset_class"]
                existing = conn.execute(
                    "SELECT id, name, asset_class FROM assets WHERE UPPER(COALESCE(ticker, symbol))=UPPER(?) LIMIT 1",
                    (ticker,),
                ).fetchone()
                now = now_iso()
                if existing:
                    conn.execute(
                        """
                        UPDATE assets
                           SET ticker=COALESCE(NULLIF(ticker, ''), ?),
                               symbol=COALESCE(NULLIF(symbol, ''), ?),
                               name=COALESCE(NULLIF(name, ''), ?),
                               asset_class=COALESCE(NULLIF(asset_class, ''), ?),
                               currency=COALESCE(NULLIF(currency, ''), ?),
                               exchange=COALESCE(NULLIF(exchange, ''), ?),
                               country=COALESCE(NULLIF(country, ''), ?),
                               source='asset_catalog',
                               is_active=1,
                               last_updated_at=?,
                               updated_at=?
                         WHERE id=?
                        """,
                        (ticker, ticker, row["name"], asset_class, row["currency"], row["market"], "BR" if row["market"] == "B3" else "GLOBAL", now, now, existing["id"]),
                    )
                    stats["updated"] += 1
                else:
                    conn.execute(
                        """
                        INSERT INTO assets
                            (symbol, ticker, name, asset_class, currency, source, country, last_updated_at, metadata_json, updated_at, exchange, is_active)
                        VALUES (?, ?, ?, ?, ?, 'asset_catalog', ?, ?, '{}', ?, ?, 1)
                        """,
                        (ticker, ticker, row["name"], asset_class, row["currency"], "BR" if row["market"] == "B3" else "GLOBAL", now, now, row["market"]),
                    )
                    stats["inserted"] += 1
            except Exception as exc:  # noqa: BLE001
                stats["errors"] += 1
                print(f"[ERRO] {row['ticker']}: {exc}")
        conn.commit()
    print("SYNC ASSETS FROM CATALOG")
    for key, value in stats.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
