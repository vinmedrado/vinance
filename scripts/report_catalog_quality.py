from __future__ import annotations

import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.data_layer.catalog.catalog_quality import summarize_assets, validate_catalog_items
from backend.app.data_layer.catalog.catalog_repository import fetch_catalog_assets


def main() -> int:
    rows = fetch_catalog_assets()
    quality = validate_catalog_items(rows)
    summary = summarize_assets(rows)
    print("=" * 80)
    print("RELATÓRIO DE QUALIDADE DO CATÁLOGO")
    print("=" * 80)
    print(f"total_ativos: {summary['total_assets']}")
    print(f"duplicados: {len(quality['duplicates'])}")
    print(f"inválidos: {len(quality['invalid_rows'])}")
    print(f"desconhecidos: {summary['unknown_assets']}")
    print("\nAtivos por classe:")
    for klass, total in summary["by_class"].items():
        print(f"- {klass}: {total}")
    print("\nAtivos por país:")
    for country, total in summary["by_country"].items():
        print(f"- {country}: {total}")
    print("\nCobertura de campos obrigatórios:")
    for field, data in summary["required_coverage"].items():
        print(f"- {field}: preenchidos={data['filled']} faltantes={data['missing']}")
    if quality["duplicates"]:
        print("\nTickers duplicados:")
        for ticker in quality["duplicates"][:50]:
            print(f"- {ticker}")
    if quality["invalid_rows"]:
        print("\nAtivos inválidos:")
        for item in quality["invalid_rows"][:50]:
            print(f"- linha={item['row']} ticker={item['ticker']} erros={'; '.join(item['errors'])}")
    print("=" * 80)
    return 0 if quality["is_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
