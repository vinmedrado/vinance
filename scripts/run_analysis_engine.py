from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from backend.app.analysis.engine import run_analysis_engine
VALID_CLASSES = ["all", "equity", "fii", "etf", "bdr", "crypto", "index", "currency", "commodity"]
def parse_tickers(value: str | None):
    return None if not value else [i.strip().upper() for i in value.split(',') if i.strip()]
def main() -> int:
    p=argparse.ArgumentParser(description='Executa a engine de análise financeira do FinanceOS.')
    p.add_argument('--asset-class', default='all', choices=VALID_CLASSES); p.add_argument('--tickers'); p.add_argument('--limit', type=int); p.add_argument('--dry-run', action='store_true'); p.add_argument('--top-n', type=int, default=30)
    a=p.parse_args(); r=run_analysis_engine(asset_class=a.asset_class,tickers=parse_tickers(a.tickers),limit=a.limit,dry_run=a.dry_run,top_n=a.top_n)
    print('='*80); print('FinanceOS Analysis Engine - PATCH 8'); print('='*80)
    print(f"Total ativos: {r['total_assets']}"); print(f"Sucesso: {r['total_success']}"); print(f"Falhas: {r['total_failed']}"); print(f"Ignorados: {r['total_skipped']}"); print(f"Dry-run: {r['dry_run']}"); print('-'*80)
    for item in r['details'][:50]: print(item)
    return 1 if r['total_failed'] else 0
if __name__ == '__main__': raise SystemExit(main())
