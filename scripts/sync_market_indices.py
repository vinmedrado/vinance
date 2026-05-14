from __future__ import annotations

import argparse
from _cli_common import add_sync_args
from backend.app.data_layer.pipelines.indices import run
from backend.app.data_layer.pipelines.logging_utils import print_summary

if __name__ == "__main__":
    parser = add_sync_args(argparse.ArgumentParser(description="Sincroniza índices de mercado."), include_incremental=True)
    args = parser.parse_args()
    result = run(incremental=args.incremental, limit=args.limit, tickers=args.tickers, start_date=args.start_date, end_date=args.end_date, dry_run=args.dry_run)
    print_summary(result)
