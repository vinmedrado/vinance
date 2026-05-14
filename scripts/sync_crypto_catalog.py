from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.asset_catalog_db import connect, ensure_asset_catalog_schema, upsert_catalog_asset
from services.asset_discovery_service import AssetDiscoveryService


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincroniza catálogo de criptoativos gratuitos.")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    service = AssetDiscoveryService()
    rows = service.fetch_top_crypto(args.limit)
    stats = {"processed": len(rows), "inserted": 0, "updated": 0, "ignored": 0, "errors": 0}
    with connect() as conn:
        ensure_asset_catalog_schema(conn)
        for row in rows:
            try:
                result = upsert_catalog_asset(conn, row)
                if result in stats:
                    stats[result] += 1
                else:
                    stats["ignored"] += 1
            except Exception as exc:  # noqa: BLE001
                stats["errors"] += 1
                print(f"[ERRO] {row.get('ticker')}: {exc}")
        conn.commit()
    print("SYNC CRYPTO CATALOG")
    for key, value in stats.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
