from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.asset_catalog_db import connect, ensure_asset_catalog_schema, fetch_catalog, update_catalog_status
from services.asset_discovery_service import AssetDiscoveryService


def _parse_dt(value: str | None):
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value)[:len(fmt)], fmt)
        except Exception:
            pass
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def is_cache_fresh(last_validated_at: str | None, max_age_days: int) -> bool:
    last = _parse_dt(last_validated_at)
    if not last:
        return False
    return datetime.utcnow() - last <= timedelta(days=max_age_days)


def main() -> None:
    parser = argparse.ArgumentParser(description='Valida catálogo de ativos via fontes gratuitas com cache e fallback.')
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--asset-class', default=None)
    parser.add_argument('--status', default='pending_validation')
    parser.add_argument('--max-age-days', type=int, default=7)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()

    service = AssetDiscoveryService()
    stats = {
        'processed': 0, 'validated': 0, 'skipped_cache': 0, 'forced_validation': 0,
        'active': 0, 'weak_data': 0, 'stale': 0, 'not_found': 0, 'unsupported': 0, 'error': 0,
    }
    source_stats = {}
    with connect() as conn:
        ensure_asset_catalog_schema(conn)
        rows = fetch_catalog(conn, asset_class=args.asset_class, status=args.status, limit=args.limit)
        for row in rows:
            stats['processed'] += 1
            try:
                if not args.force and is_cache_fresh(row['last_validated_at'], args.max_age_days):
                    stats['skipped_cache'] += 1
                    print(f"[CACHE] {row['ticker']} | status={row['api_status']} | last_validated_at={row['last_validated_at']}")
                    continue
                if args.force:
                    stats['forced_validation'] += 1
                result = service.validate(row['ticker'], row['yahoo_symbol'], row['asset_class'], row['source_priority'])
                update_catalog_status(conn, row['id'], result.status, result.notes, source_used=result.source)
                stats['validated'] += 1
                stats[result.status] = stats.get(result.status, 0) + 1
                source_stats[result.source] = source_stats.get(result.source, 0) + 1
                print(f"[{result.status.upper()}] {row['ticker']} | {row['yahoo_symbol']} | source={result.source} | {result.notes or ''}")
            except Exception as exc:  # noqa: BLE001
                stats['error'] += 1
                update_catalog_status(conn, row['id'], 'error', f'Falha inesperada na validação: {exc}', source_used='validator')
                print(f"[ERROR] {row['ticker']} | {exc}")
        conn.commit()
    print('VALIDATE ASSET CATALOG')
    for key, value in stats.items():
        print(f'- {key}: {value}')
    print('- source_used:')
    for key, value in sorted(source_stats.items()):
        print(f'  - {key}: {value}')


if __name__ == '__main__':
    main()
