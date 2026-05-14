from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from services.asset_catalog_db import connect, ensure_asset_catalog_schema, normalize_ticker, infer_yahoo_symbol, upsert_catalog_asset

SHEET_CLASS_HINTS = {
    "acoes": "equity", "ações": "equity", "acao": "equity", "ação": "equity", "equities": "equity", "stocks": "equity",
    "fiis": "fii", "fii": "fii", "fundos": "fii",
    "etf": "etf", "etfs": "etf",
    "bdr": "bdr", "bdrs": "bdr",
}

TICKER_COLUMNS = {"codigo", "código", "ticker", "mercados", "mercado", "symbol", "ativo"}
NAME_COLUMNS = {"nome", "name", "empresa", "companhia", "descrição", "descricao", "description"}


def infer_asset_class(sheet_name: str) -> str:
    normalized = sheet_name.strip().lower()
    for key, value in SHEET_CLASS_HINTS.items():
        if key in normalized:
            return value
    return "equity"


def find_column(columns: list[str], candidates: set[str]) -> str | None:
    clean = {str(c).strip().lower(): c for c in columns}
    for normalized, original in clean.items():
        if normalized in candidates:
            return original
    for normalized, original in clean.items():
        if any(candidate in normalized for candidate in candidates):
            return original
    return None


def read_excel_assets(path: Path) -> list[dict[str, Any]]:
    sheets = pd.read_excel(path, sheet_name=None)
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for sheet_name, df in sheets.items():
        if df.empty:
            continue
        df.columns = [str(c).strip() for c in df.columns]
        asset_class = infer_asset_class(sheet_name)
        ticker_col = find_column(list(df.columns), TICKER_COLUMNS)
        name_col = find_column(list(df.columns), NAME_COLUMNS)
        if not ticker_col:
            # fallback: first column with non-empty strings
            ticker_col = df.columns[0]
        for _, row in df.iterrows():
            ticker = normalize_ticker(row.get(ticker_col))
            if not ticker or ticker.lower() in {"nan", "none"}:
                continue
            if len(ticker) > 20:
                continue
            key = (ticker, asset_class)
            if key in seen:
                continue
            seen.add(key)
            name = str(row.get(name_col)).strip() if name_col and row.get(name_col) is not None else ticker
            if name.lower() in {"nan", "none", ""}:
                name = ticker
            market = "B3" if asset_class in {"equity", "fii", "etf", "bdr"} else "global"
            items.append({
                "ticker": ticker,
                "yahoo_symbol": infer_yahoo_symbol(ticker, asset_class, market),
                "name": name,
                "asset_class": asset_class,
                "market": market,
                "currency": "BRL" if market == "B3" else "USD",
                "source": "excel_seed",
                "api_status": "pending_validation",
                "notes": f"seed_sheet={sheet_name}; ticker_column={ticker_col}",
            })
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa catálogo de ativos de um Excel como seed inicial.")
    parser.add_argument("--file", required=True, help="Caminho do Excel. Ex: data/imports/b3.xlsx")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise SystemExit(f"Arquivo não encontrado: {path}")

    items = read_excel_assets(path)
    stats = {"processed": len(items), "inserted": 0, "updated": 0, "ignored": 0, "errors": 0}
    with connect() as conn:
        ensure_asset_catalog_schema(conn)
        for item in items:
            try:
                result = upsert_catalog_asset(conn, item)
                if result in stats:
                    stats[result] += 1
                else:
                    stats["ignored"] += 1
            except Exception as exc:  # noqa: BLE001
                stats["errors"] += 1
                print(f"[ERRO] {item.get('ticker')}: {exc}")
        conn.commit()
    print("IMPORT ASSET CATALOG FROM EXCEL")
    for key, value in stats.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
