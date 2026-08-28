"""Diagnóstico controlado do endpoint advancedsearchresult para FIIs.

Investiga CategoryType de FIIs sem operacionalizar provider. Por padrão testa candidatos
leves e imprime campos retornados para confirmar pvp, dy, liquidez, segmento, patrimonio e vpa.

Uso:
  python scripts/statusinvest_diagnostics/test_fiis_search.py
  python scripts/statusinvest_diagnostics/test_fiis_search.py --category-type 2 --save-raw
"""
from __future__ import annotations

import json
import time
from typing import Any

from common import (
    ADVANCED_SEARCH_ENDPOINT,
    build_advanced_search_params,
    configure_logging,
    print_summary,
    range_filter,
    request_json,
    save_raw_if_requested,
    base_parser,
    summarize_json,
)

FIIS_REFERER = "https://statusinvest.com.br/fundos-imobiliarios/busca-avancada"
DEFAULT_FII_CATEGORY_CANDIDATES = [2, 3, 4]
TARGET_FIELDS = ["pvp", "dy", "liquidez", "segmento", "patrimonio", "vpa"]


def build_fiis_payload() -> dict:
    """Payload diagnóstico com campos historicamente prováveis para busca avançada de FIIs."""

    return {
        "Segment": "",
        "my_range": "-20;100",
        "dy": range_filter(),
        "p_VP": range_filter(),
        "valorPatrimonial": range_filter(),
        "liquidezMediaDiaria": range_filter(),
        "vpa": range_filter(),
        "patrimonioLiquido": range_filter(),
    }


def flatten_field_names(payload: Any) -> set[str]:
    fields: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            fields.add(str(key))
            fields.update(flatten_field_names(value))
    elif isinstance(payload, list):
        for item in payload[:10]:
            fields.update(flatten_field_names(item))
    return fields


def analyze_target_fields(payload: Any) -> dict[str, list[str]]:
    fields = sorted(flatten_field_names(payload))
    lower_map = {field.lower(): field for field in fields}
    found: dict[str, list[str]] = {}
    for target in TARGET_FIELDS:
        matches = [original for lowered, original in lower_map.items() if target in lowered]
        found[target] = matches[:20]
    return found


def main() -> int:
    parser = base_parser("Diagnóstico XHR Status Invest - FIIs / advancedsearchresult")
    parser.add_argument(
        "--category-type",
        type=int,
        default=None,
        help="Força um CategoryType específico. Se omitido, testa candidatos 2, 3 e 4.",
    )
    args = parser.parse_args()
    configure_logging(args.verbose)

    payload = build_fiis_payload()
    candidates = [args.category_type] if args.category_type is not None else DEFAULT_FII_CATEGORY_CANDIDATES
    print("\nPayload enviado para FIIs:")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:5000])
    print(f"\nCategoryTypes candidatos para FIIs: {candidates}")

    best_status = 0
    for index, category_type in enumerate(candidates, start=1):
        params = build_advanced_search_params(payload, category_type)
        result = request_json(
            url=ADVANCED_SEARCH_ENDPOINT,
            params=params,
            referer=FIIS_REFERER,
            timeout_seconds=args.timeout,
            retries=args.retries,
            sleep_seconds=args.sleep,
        )
        print_summary(f"Diagnóstico advancedsearchresult - FIIs | CategoryType={category_type}", result)
        print("Campos-alvo encontrados por substring:")
        print(json.dumps(analyze_target_fields(result.json_payload), ensure_ascii=False, indent=2))
        print("Resumo compacto para comparação de candidato:")
        print(json.dumps(summarize_json(result.json_payload, max_rows=1), ensure_ascii=False, indent=2, default=str)[:4000])
        save_raw_if_requested(
            result,
            prefix=f"fiis_advancedsearchresult_category_{category_type}",
            save_raw=args.save_raw,
        )
        if result.status_code and result.status_code < 500:
            best_status = 0
        if index < len(candidates):
            time.sleep(args.sleep)

    return best_status


if __name__ == "__main__":
    raise SystemExit(main())
