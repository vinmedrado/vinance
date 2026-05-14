from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def add_sync_args(parser: argparse.ArgumentParser, include_incremental: bool = False) -> argparse.ArgumentParser:
    if include_incremental:
        parser.add_argument("--incremental", action="store_true", help="Executa em modo incremental.")
    parser.add_argument("--limit", type=int, default=None, help="Limita a quantidade de itens processados.")
    parser.add_argument("--tickers", type=str, default=None, help="Lista separada por vírgula. Ex: PETR4,VALE3 ou SELIC,IPCA.")
    parser.add_argument("--start-date", dest="start_date", type=str, default=None, help="Data inicial YYYY-MM-DD.")
    parser.add_argument("--end-date", dest="end_date", type=str, default=None, help="Data final YYYY-MM-DD.")
    parser.add_argument("--dry-run", action="store_true", help="Executa sem gravar no banco.")
    return parser
