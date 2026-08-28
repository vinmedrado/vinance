from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.app.core.logging import get_logger

logger = get_logger(__name__)

SOURCE_JSON = "statusinvest_json"
SOURCE_HTML_FALLBACK = "statusinvest_html_fallback"
SOURCE_MISSING = "statusinvest_missing"

ACAO_FIELD_MAPPING = {
    "p_L": "pl",
    "pL": "pl",
    "pl": "pl",
    "p_VP": "pvp",
    "pVP": "pvp",
    "pvp": "pvp",
    "p_SR": "psr",
    "pSR": "psr",
    "psr": "psr",
    "eV_Ebitda": "ev_ebitda",
    "evEbitda": "ev_ebitda",
    "ev_Ebitda": "ev_ebitda",
    "eV_Ebit": "ev_ebit",
    "evEbit": "ev_ebit",
    "ev_Ebit": "ev_ebit",
    "roe": "roe",
    "roa": "roa",
    "roic": "roic",
    "margemLiquida": "margem_liquida",
    "margem_liquida": "margem_liquida",
    "margemEbitda": "margem_ebitda",
    "margem_ebitda": "margem_ebitda",
    "dy": "dy_12m",
    "dividendYield": "dy_12m",
    "dividaLiquidaEbitda": "divida_liq_ebitda",
    "divida_liq_ebitda": "divida_liq_ebitda",
    "dividaLiquidaEbit": "divida_liq_ebitda",
    "liquidezMediaDiaria": "volume_medio_diario",
    "liquidez": "volume_medio_diario",
    "valorMercado": "market_cap",
    "valor_mercado": "market_cap",
    "price": "price",
    "preco": "price",
    "cotacao": "price",
    "setor": "setor",
    "sector": "setor",
    "subsetor": "subsetor",
    "subSector": "subsetor",
}

FII_FIELD_MAPPING = {
    "p_VP": "pvp",
    "pVP": "pvp",
    "pvp": "pvp",
    "dy": "dy_12m",
    "dividendYield": "dy_12m",
    "liquidezMediaDiaria": "liquidez_diaria",
    "liquidez": "liquidez_diaria",
    "segmento": "segmento",
    "segment": "segmento",
    "tipo": "tipo",
    "type": "tipo",
    "patrimonioLiquido": "patrimonio_liq",
    "patrimonio": "patrimonio_liq",
    "valorPatrimonial": "patrimonio_liq",
    "valor_patrimonial": "patrimonio_liq",
    "vpa": "vpa",
    "price": "price",
    "preco": "price",
    "cotacao": "price",
    "numCotistas": "num_cotistas",
    "numeroCotistas": "num_cotistas",
    "cotistas": "num_cotistas",
    "vacanciaFisica": "vacancia_fisica",
    "vacanciaFinanceira": "vacancia_financeira",
    "gestora": "gestora",
    "administradora": "administradora",
    "taxaAdm": "taxa_adm",
    "taxaAdministracao": "taxa_adm",
    "numImoveis": "num_imoveis",
    "numeroImoveis": "num_imoveis",
}

ACAO_ALLOWED_FIELDS = {
    "ticker",
    "name",
    "date",
    "price",
    "market_cap",
    "pl",
    "pvp",
    "psr",
    "ev_ebitda",
    "ev_ebit",
    "roe",
    "roa",
    "roic",
    "margem_liquida",
    "margem_ebitda",
    "dy_12m",
    "divida_liq_ebitda",
    "volume_medio_diario",
    "setor",
    "subsetor",
    "source",
}

FII_ALLOWED_FIELDS = {
    "ticker",
    "name",
    "date",
    "price",
    "patrimonio_liq",
    "vpa",
    "pvp",
    "dy_12m",
    "volume_medio_diario",
    "liquidez_diaria",
    "tipo",
    "segmento",
    "num_cotistas",
    "num_imoveis",
    "vacancia_fisica",
    "vacancia_financeira",
    "gestora",
    "administradora",
    "taxa_adm",
    "source",
}

ROW_LIST_KEYS = ("data", "list", "results", "items", "result", "stocks", "funds")
TICKER_KEYS = ("ticker", "code", "symbol", "tickerName", "tickername", "companyName", "companyname", "company", "name")
NAME_KEYS = ("companyName", "companyname", "name", "nome", "razaoSocial", "razaosocial", "tickerName", "tickername")


def _parse_string_payload(payload: str) -> Any:
    text = payload.strip()
    if not text:
        return []
    if text.startswith("<"):
        logger.warning("Status Invest returned HTML for JSON endpoint", extra={"content_preview": text[:80]})
        return []
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Status Invest returned non-JSON string payload", extra={"content_preview": text[:120]})
        return []


def _rows_from_value(value: Any, *, depth: int = 0) -> list[dict[str, Any]]:
    if depth > 4:
        return []
    if isinstance(value, str):
        return _rows_from_value(_parse_string_payload(value), depth=depth + 1)
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if not isinstance(value, dict):
        return []

    for key in ROW_LIST_KEYS:
        nested = value.get(key)
        if isinstance(nested, (list, dict, str)):
            rows = _rows_from_value(nested, depth=depth + 1)
            if rows:
                return rows

    for nested in value.values():
        if isinstance(nested, (list, dict, str)):
            rows = _rows_from_value(nested, depth=depth + 1)
            if rows:
                return rows
    return []


def describe_payload(payload: Any) -> dict[str, Any]:
    parsed = _parse_string_payload(payload) if isinstance(payload, str) else payload
    rows = _rows_from_value(parsed)
    first = rows[0] if rows else None
    return {
        "payload_type": type(parsed).__name__,
        "dict_keys": list(parsed.keys())[:20] if isinstance(parsed, dict) else [],
        "row_count": len(rows),
        "first_row_keys": list(first.keys())[:30] if isinstance(first, dict) else [],
    }


def extract_rows(payload: Any) -> list[dict[str, Any]]:
    return _rows_from_value(payload)


def normalize_ticker(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    # Common Status Invest shapes include "PETR4", "PETR4 - PETROBRAS" or names containing the ticker.
    token_match = re.search(r"\b[A-Z]{4}\d{1,2}[A-Z]?\b", text)
    if token_match:
        return token_match.group(0)
    ticker = re.sub(r"[^A-Z0-9]", "", text)
    return ticker or None


def row_ticker(row: dict[str, Any]) -> str | None:
    for key in TICKER_KEYS:
        ticker = normalize_ticker(row.get(key))
        if ticker and 5 <= len(ticker) <= 8:
            return ticker
    return None


def row_name(row: dict[str, Any], fallback: str) -> str:
    for key in NAME_KEYS:
        value = row.get(key)
        if value:
            return str(value).strip()[:255]
    return fallback


def to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    text = str(value).strip()
    if not text or text in {"-", "--", "N/A", "n/a", "null", "None"}:
        return None
    text = text.replace("R$", "").replace("%", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def to_int(value: Any) -> int | None:
    decimal = to_decimal(value)
    if decimal is None:
        return None
    try:
        return int(decimal)
    except (ValueError, TypeError, OverflowError):
        return None


def _copy_mapped_fields(row: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for source_key, target_key in mapping.items():
        if source_key in row:
            raw = row.get(source_key)
            if target_key in {"setor", "subsetor", "segmento", "tipo", "gestora", "administradora"}:
                output[target_key] = str(raw).strip()[:160] if raw not in (None, "") else None
            elif target_key in {"num_cotistas", "num_imoveis"}:
                output[target_key] = to_int(raw)
            else:
                output[target_key] = to_decimal(raw)
    return output


def normalize_acoes(payload: Any, *, allowed_tickers: set[str] | None = None, reference_date: date | None = None) -> list[dict[str, Any]]:
    rows = extract_rows(payload)
    normalized: list[dict[str, Any]] = []
    for row in rows:
        ticker = row_ticker(row)
        if not ticker or (allowed_tickers is not None and ticker not in allowed_tickers):
            continue
        item = _copy_mapped_fields(row, ACAO_FIELD_MAPPING)
        item.update({"ticker": ticker, "name": row_name(row, ticker), "date": reference_date or date.today(), "source": SOURCE_JSON})
        normalized.append({key: value for key, value in item.items() if key in ACAO_ALLOWED_FIELDS})
    return normalized


def normalize_fiis(payload: Any, *, allowed_tickers: set[str] | None = None, reference_date: date | None = None) -> list[dict[str, Any]]:
    rows = extract_rows(payload)
    normalized: list[dict[str, Any]] = []
    for row in rows:
        ticker = row_ticker(row)
        if not ticker or (allowed_tickers is not None and ticker not in allowed_tickers):
            continue
        item = _copy_mapped_fields(row, FII_FIELD_MAPPING)
        if item.get("volume_medio_diario") is None and item.get("liquidez_diaria") is not None:
            item["volume_medio_diario"] = item["liquidez_diaria"]
        item.update({"ticker": ticker, "name": row_name(row, ticker), "date": reference_date or date.today(), "source": SOURCE_JSON})
        normalized.append({key: value for key, value in item.items() if key in FII_ALLOWED_FIELDS})
    return normalized


def merge_html_fallback(item: dict[str, Any], fallback: dict[str, Any], *, market: str) -> tuple[dict[str, Any], str]:
    if not fallback:
        return item, "json"
    changed = False
    allowed = FII_ALLOWED_FIELDS if market == "fii" else ACAO_ALLOWED_FIELDS
    output = dict(item)
    for key, value in fallback.items():
        if key in allowed and output.get(key) is None and value is not None:
            output[key] = value
            changed = True
    if changed:
        output["source"] = SOURCE_HTML_FALLBACK
        return output, "html_fallback"
    return output, "json"
