from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.data_layer.catalog.catalog_builder import sync_massive_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="PATCH 7 — sincroniza catálogo massivo de ativos.")
    parser.add_argument("--source", choices=["all", "fallback", "yfinance", "b3"], default="fallback")
    parser.add_argument("--asset-class", dest="asset_class", choices=["all", "equity", "fii", "etf", "bdr", "crypto", "index", "currency", "commodity"], default="all")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = sync_massive_catalog(args.source, args.asset_class, args.limit, args.dry_run)
    print("=" * 80)
    print("PATCH 7 — CATÁLOGO MASSIVO")
    print("=" * 80)
    print(f"source={result['source']} asset_class={result['asset_class']} dry_run={result['dry_run']}")
    print(f"carregados={result['loaded']} válidos={result['valid']} inválidos={result['invalid']}")
    print(f"inseridos={result['inserted']} atualizados={result['updated']} ignorados={result['skipped']}")
    if result["quality"]["invalid_rows"]:
        print("\nInconsistências encontradas:")
        for item in result["quality"]["invalid_rows"][:20]:
            print(f"- linha={item['row']} ticker={item['ticker']} erros={'; '.join(item['errors'])}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
