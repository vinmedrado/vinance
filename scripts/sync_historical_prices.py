from __future__ import annotations

import argparse
from _cli_common import add_sync_args
from backend.app.data_layer.pipelines.historical_prices import run
from backend.app.data_layer.pipelines.logging_utils import print_summary

if __name__ == "__main__":
    parser = add_sync_args(argparse.ArgumentParser(description="Sincroniza preços históricos."), include_incremental=True)
    parser.add_argument(
        "--asset-class",
        dest="asset_class",
        default=None,
        help="Filtra classe de ativo. Ex: equity, fii, etf, bdr, crypto. Use equity para puxar todas as ações brasileiras cadastradas.",
    )
    args = parser.parse_args()
    result = run(
        incremental=args.incremental,
        limit=args.limit,
        tickers=args.tickers,
        start_date=args.start_date,
        end_date=args.end_date,
        dry_run=args.dry_run,
        asset_class=args.asset_class,
    )
    print_summary(result)
