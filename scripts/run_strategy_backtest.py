import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.backtest.strategies.strategy_runner import StrategyBacktestRunner


def _tickers(value: str):
    return [t.strip().upper() for t in value.split(',') if t.strip()] or None


def parse_args():
    parser = argparse.ArgumentParser(description='FinanceOS PATCH 10 - Backtest de estratégias avançadas')
    parser.add_argument('--strategy', default='score_top_n', choices=['score_top_n','momentum','dividend_yield','low_volatility','multi_factor'])
    parser.add_argument('--asset-class', default='all', choices=['all','equity','fii','etf','bdr','crypto','index','currency','commodity'])
    parser.add_argument('--start-date', default='2020-01-01')
    parser.add_argument('--end-date', default='2024-01-01')
    parser.add_argument('--initial-capital', type=float, default=10000.0)
    parser.add_argument('--top-n', type=int, default=10)
    parser.add_argument('--rebalance', '--rebalance-frequency', dest='rebalance_frequency', default='monthly', choices=['daily','weekly','monthly'])
    parser.add_argument('--transaction-cost', type=float, default=0.001)
    parser.add_argument('--min-score', type=float, default=None)
    parser.add_argument('--max-position-pct', type=float, default=0.15)
    parser.add_argument('--min-liquidity-score', type=float, default=None)
    parser.add_argument('--tickers', default='')
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--mode', default='no_lookahead', choices=['no_lookahead','research'])
    parser.add_argument('--weight-return', type=float, default=0.25)
    parser.add_argument('--weight-risk', type=float, default=0.20)
    parser.add_argument('--weight-liquidity', type=float, default=0.15)
    parser.add_argument('--weight-dividend', type=float, default=0.20)
    parser.add_argument('--weight-trend', type=float, default=0.20)
    parser.add_argument('--require-above-mm200', action='store_true')
    parser.add_argument('--turnover-control-enabled', dest='turnover_control_enabled', action='store_true', default=True)
    parser.add_argument('--disable-turnover-control', dest='turnover_control_enabled', action='store_false')
    parser.add_argument('--hysteresis-buffer', type=int, default=2)
    parser.add_argument('--min-holding-period-rebalances', type=int, default=2)
    return parser.parse_args()


def main():
    args = parse_args()
    runner = StrategyBacktestRunner()
    result = runner.run(
        strategy=args.strategy,
        asset_class=args.asset_class,
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.initial_capital,
        top_n=args.top_n,
        rebalance_frequency=args.rebalance_frequency,
        transaction_cost=args.transaction_cost,
        min_score=args.min_score,
        max_position_pct=args.max_position_pct,
        min_liquidity_score=args.min_liquidity_score,
        tickers=_tickers(args.tickers),
        dry_run=args.dry_run,
        mode=args.mode,
        limit=args.limit,
        weight_return=args.weight_return,
        weight_risk=args.weight_risk,
        weight_liquidity=args.weight_liquidity,
        weight_dividend=args.weight_dividend,
        weight_trend=args.weight_trend,
        require_above_mm200=args.require_above_mm200,
        turnover_control_enabled=args.turnover_control_enabled,
        hysteresis_buffer=args.hysteresis_buffer,
        min_holding_period_rebalances=args.min_holding_period_rebalances,
    )
    print('\nBACKTEST DE ESTRATÉGIA FINALIZADO')
    print('=' * 80)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
