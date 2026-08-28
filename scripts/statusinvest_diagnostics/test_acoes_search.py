"""Diagnóstico controlado do endpoint advancedsearchresult para ações.

Uso:
  python scripts/statusinvest_diagnostics/test_acoes_search.py
  python scripts/statusinvest_diagnostics/test_acoes_search.py --save-raw --verbose

Não persiste dados em banco e não integra provider operacional.
"""
from __future__ import annotations

import json

from common import (
    ADVANCED_SEARCH_ENDPOINT,
    build_advanced_search_params,
    configure_logging,
    print_summary,
    range_filter,
    request_json,
    save_raw_if_requested,
    base_parser,
)

ACOES_REFERER = "https://statusinvest.com.br/acoes/busca-avancada"
ACOES_CATEGORY_TYPE = 1


def build_acoes_payload() -> dict:
    """Payload amplo, conservador e sem filtros restritivos para mapear nomes reais dos campos."""

    return {
        "Sector": "",
        "SubSector": "",
        "Segment": "",
        "my_range": "-20;100",
        "dy": range_filter(),
        "p_L": range_filter(),
        "peg_Ratio": range_filter(),
        "p_VP": range_filter(),
        "p_Ativo": range_filter(),
        "margemBruta": range_filter(),
        "margemEbit": range_filter(),
        "margemLiquida": range_filter(),
        "p_Ebit": range_filter(),
        "eV_Ebit": range_filter(),
        "dividaLiquidaEbit": range_filter(),
        "dividaLiquidaPatrimonioLiquido": range_filter(),
        "p_SR": range_filter(),
        "p_CapitalGiro": range_filter(),
        "p_AtivoCirculanteLiquido": range_filter(),
        "roe": range_filter(),
        "roic": range_filter(),
        "roa": range_filter(),
        "liquidezCorrente": range_filter(),
        "patrimonioAtivo": range_filter(),
        "passivoAtivo": range_filter(),
        "giroAtivos": range_filter(),
        "cagrReceitas5Anos": range_filter(),
        "cagrLucros5Anos": range_filter(),
        "liquidezMediaDiaria": range_filter(),
        "vpa": range_filter(),
        "lpa": range_filter(),
        "valorMercado": range_filter(),
    }


def main() -> int:
    parser = base_parser("Diagnóstico XHR Status Invest - ações / advancedsearchresult")
    args = parser.parse_args()
    configure_logging(args.verbose)

    payload = build_acoes_payload()
    params = build_advanced_search_params(payload, ACOES_CATEGORY_TYPE)
    print("\nPayload enviado para ações:")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:5000])
    print(f"\nCategoryType esperado para ações: {ACOES_CATEGORY_TYPE}")

    result = request_json(
        url=ADVANCED_SEARCH_ENDPOINT,
        params=params,
        referer=ACOES_REFERER,
        timeout_seconds=args.timeout,
        retries=args.retries,
        sleep_seconds=args.sleep,
    )
    print_summary("Diagnóstico advancedsearchresult - AÇÕES", result)
    save_raw_if_requested(result, prefix="acoes_advancedsearchresult", save_raw=args.save_raw)
    return 0  # diagnóstico controlado: falhas HTTP/rede são reportadas no log, não quebram o script


if __name__ == "__main__":
    raise SystemExit(main())
