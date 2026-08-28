from __future__ import annotations

import csv
import os
import re
from pathlib import Path
from typing import Iterable

TICKER_RE = re.compile(r"^[A-Z]{4}[0-9]{1,2}[A-Z]?$|^[A-Z]{5}[0-9]{1,2}$")

# Diretórios lidos em ordem: primeiro catálogo externo/real do usuário, depois seeds do projeto.
_DEFAULT_DIRS = (
    os.getenv("VINANCE_CATALOG_DIR"),
    "data/catalog_fallback",
    "data/catalogs",
)


def normalize_tickers(tickers: Iterable[str]) -> list[str]:
    clean: set[str] = set()
    for raw in tickers or []:
        ticker = str(raw or "").strip().upper().replace(".SA", "")
        if not ticker:
            continue
        if not TICKER_RE.match(ticker):
            continue
        clean.add(ticker)
    return sorted(clean)


def _read_csv_tickers(path: Path) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = {name.lower(): name for name in (reader.fieldnames or [])}
            ticker_field = fieldnames.get("ticker") or fieldnames.get("symbol") or fieldnames.get("codigo")
            if not ticker_field:
                return []
            return [row.get(ticker_field, "") for row in reader]
    except OSError:
        return []


def load_catalog(market: str, fallback: Iterable[str]) -> list[str]:
    """Load and sanitize a market catalog.

    Supports complete user/project catalogs without hard-coding task test lists.
    If VINANCE_CATALOG_DIR points to CSVs named fiis.csv, acoes.csv, etfs.csv or
    bdrs.csv, those tickers are merged with the project fallback and embedded seed.
    """
    market_key = market.strip().lower()
    candidates = {
        "fiis": ("fiis.csv", "brazil_fiis.csv"),
        "acoes": ("acoes.csv", "brazil_equities.csv"),
        "etfs": ("etfs.csv", "brazil_etfs.csv"),
        "bdrs": ("bdrs.csv", "brazil_bdrs.csv"),
    }.get(market_key, (f"{market_key}.csv",))

    loaded: list[str] = []
    for directory in _DEFAULT_DIRS:
        if not directory:
            continue
        base = Path(directory)
        for filename in candidates:
            loaded.extend(_read_csv_tickers(base / filename))

    return normalize_tickers([*loaded, *list(fallback or [])])
