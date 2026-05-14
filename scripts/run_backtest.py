import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.backtest.backtest_engine import BacktestEngine
from backend.app.backtest.backtest_repository import BacktestRepository


def parse_args():
    parser = argparse.ArgumentParser(description='FinanceOS PATCH 9 - Backtest Engine')
    parser.add_argument('--strategy', default='score_top_n')
    parser.add_argument('--asset-class', default='all', choices=['all','equity','fii','etf','bdr','crypto','index','currency','commodity'])
    parser.add_argument('--start-date', default='2020-01-01')
    parser.add_argument('--end-date', default='2024-01-01')
    parser.add_argument('--initial-capital', type=float, default=10000.0)
    parser.add_argument('--top-n', type=int, default=5)
    parser.add_argument('--rebalance', default='monthly', choices=['daily','weekly','monthly'])
    parser.add_argument('--tickers', default='')
    parser.add_argument('--min-score', type=float, default=None)
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--mode', default='no_lookahead', choices=['no_lookahead','research'])
    return parser.parse_args()


def main():
    args = parse_args()
    tickers = [t.strip().upper() for t in args.tickers.split(',') if t.strip()] or None
    repo = BacktestRepository()
    engine = BacktestEngine(repo)
    result = engine.run(
        strategy=args.strategy,
        asset_class=args.asset_class,
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.initial_capital,
        top_n=args.top_n,
        rebalance=args.rebalance,
        min_score=args.min_score,
        tickers=tickers,
        dry_run=args.dry_run,
        mode=args.mode,
        limit=args.limit,
    )
    print('\nBACKTEST FINALIZADO')
    print('=' * 80)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
