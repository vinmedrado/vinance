from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from bs4 import BeautifulSoup

_NUMERIC_LABELS_FII = {
    "vacância física": "vacancia_fisica",
    "vacancia física": "vacancia_fisica",
    "vacância financeira": "vacancia_financeira",
    "vacancia financeira": "vacancia_financeira",
    "taxa de administração": "taxa_adm",
    "taxa administração": "taxa_adm",
    "nº de imóveis": "num_imoveis",
    "n° de imóveis": "num_imoveis",
    "número de imóveis": "num_imoveis",
    "quantidade de imóveis": "num_imoveis",
}

_TEXT_LABELS_FII = {
    "gestora": "gestora",
    "administradora": "administradora",
}

_NUMERIC_LABELS_ACAO = {
    "margem líquida": "margem_liquida",
    "margem liquida": "margem_liquida",
    "margem ebitda": "margem_ebitda",
    "dívida líquida/ebitda": "divida_liq_ebitda",
    "divida liquida/ebitda": "divida_liq_ebitda",
    "ev/ebitda": "ev_ebitda",
    "ev/ebit": "ev_ebit",
}


def _clean_label(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip().lower()
    return value.replace(":", "")


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text or text in {"-", "--"}:
        return None
    text = text.replace("R$", "").replace("%", "").strip()
    text = re.sub(r"[^0-9,.-]", "", text)
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _parse_int(value: Any) -> int | None:
    decimal = _parse_decimal(value)
    if decimal is None:
        return None
    try:
        return int(decimal)
    except (ValueError, TypeError, OverflowError):
        return None


def _semantic_pairs(soup: BeautifulSoup) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for node in soup.find_all(string=True):
        label = _clean_label(str(node))
        if not label or len(label) > 80:
            continue
        parent = getattr(node, "parent", None)
        if parent is None:
            continue
        candidates: list[str] = []
        for sibling in parent.find_all_next(string=True, limit=4):
            text = re.sub(r"\s+", " ", str(sibling)).strip()
            if text and _clean_label(text) != label:
                candidates.append(text)
        if candidates:
            pairs.append((label, candidates[0]))
    return pairs


def parse_fii_fallback(html: str | None) -> dict[str, Any]:
    if not html:
        return {}
    soup = BeautifulSoup(html, "html.parser")
    output: dict[str, Any] = {}
    for label, value in _semantic_pairs(soup):
        if label in _NUMERIC_LABELS_FII:
            key = _NUMERIC_LABELS_FII[label]
            output[key] = _parse_int(value) if key == "num_imoveis" else _parse_decimal(value)
        elif label in _TEXT_LABELS_FII:
            output[_TEXT_LABELS_FII[label]] = value[:160]
    return {key: value for key, value in output.items() if value not in (None, "")}


def parse_acao_fallback(html: str | None) -> dict[str, Any]:
    if not html:
        return {}
    soup = BeautifulSoup(html, "html.parser")
    output: dict[str, Any] = {}
    for label, value in _semantic_pairs(soup):
        if label in _NUMERIC_LABELS_ACAO:
            output[_NUMERIC_LABELS_ACAO[label]] = _parse_decimal(value)
    return {key: value for key, value in output.items() if value is not None}
