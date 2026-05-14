from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.data_layer.repositories.sqlite_repository import connect, ensure_patch6_schema, insert_macro_rows, insert_index_rows, upsert_asset
from backend.app.data_layer.utils.date_utils import today_iso

ASSETS = [
    {"ticker": "PETR4", "name": "Petrobras PN", "asset_class": "equity", "country": "BR", "currency": "BRL", "source": "seed_minimal"},
    {"ticker": "MXRF11", "name": "Maxi Renda FII", "asset_class": "fii", "country": "BR", "currency": "BRL", "source": "seed_minimal"},
    {"ticker": "IVVB11", "name": "iShares S&P 500 ETF", "asset_class": "etf", "country": "BR", "currency": "BRL", "source": "seed_minimal"},
]


def main() -> int:
    inserted = updated = 0
    with connect() as conn:
        ensure_patch6_schema(conn)
        for asset in ASSETS:
            _, created = upsert_asset(conn, asset)
            inserted += int(created)
            updated += int(not created)
        idx = insert_index_rows(conn, "IBOV", "Ibovespa", [{"date": today_iso(), "close": None, "volume": None, "source": "seed_minimal"}])
        macro = insert_macro_rows(conn, [{"code": "11", "name": "SELIC", "date": today_iso(), "value": None, "source": "seed_minimal"}])
    print(f"Seed mínimo concluído. Assets inseridos={inserted}, assets existentes/atualizados={updated}, índices={idx}, macro={macro}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
