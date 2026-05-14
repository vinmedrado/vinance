from __future__ import annotations

import argparse
from db import pg_compat as dbcompat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.asset_catalog_db import ROOT_DIR
from services.asset_quality_service import (
    calculate_asset_quality,
    ensure_asset_quality_columns,
    get_asset_price_stats,
    update_asset_quality,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Atualiza scores de qualidade do asset_catalog.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--asset-class", default=None)
    parser.add_argument("--status", default=None, help="api_status: active, pending_validation, error, etc.")
    parser.add_argument("--ticker", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    counters = {"processed": 0, "updated": 0, "errors": 0, "excellent": 0, "good": 0, "usable": 0, "weak_data": 0, "invalid": 0, "unknown": 0}
    with dbcompat.connect(ROOT_DIR) as conn:
        conn.row_factory = dbcompat.Row
        ensure_asset_quality_columns(conn)
        sql = "SELECT * FROM asset_catalog WHERE 1=1"
        params = []
        if args.asset_class:
            sql += " AND LOWER(asset_class)=LOWER(?)"
            params.append(args.asset_class)
        if args.status:
            sql += " AND LOWER(api_status)=LOWER(?)"
            params.append(args.status)
        if args.ticker:
            sql += " AND UPPER(ticker)=UPPER(?)"
            params.append(args.ticker)
        sql += " ORDER BY asset_class, ticker"
        if args.limit:
            sql += " LIMIT ?"
            params.append(int(args.limit))
        assets = conn.execute(sql, params).fetchall()
        print(f"[quality] ativos encontrados: {len(assets)}")
        for row in assets:
            counters["processed"] += 1
            try:
                asset = dict(row)
                stats = get_asset_price_stats(conn, asset.get("ticker"))
                quality = calculate_asset_quality(asset, stats)
                update_asset_quality(conn, int(asset["id"]), quality)
                counters["updated"] += 1
                rel = quality.get("reliability_status", "unknown")
                counters[rel] = counters.get(rel, 0) + 1
                print(
                    f"[quality] {asset.get('ticker')} | score={quality['data_quality_score']} | "
                    f"status={rel} | records={quality['price_records']} | history_days={quality['history_days']}"
                )
            except Exception as exc:
                counters["errors"] += 1
                print(f"[quality][ERROR] {row['ticker']}: {exc}")
        conn.commit()
    print("\n[quality] resumo")
    for key, value in counters.items():
        print(f"  - {key}: {value}")
    return 0 if counters["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
