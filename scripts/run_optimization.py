import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.backtest.optimization.grid_search import GridSearchOptimizer, parse_values
from backend.app.backtest.optimization.walk_forward import WalkForwardOptimizer


def parse_float_or_none(value: str):
    if value.lower() in {'none', 'null', ''}:
        return None
    return float(value)


def parse_args():
    parser = argparse.ArgumentParser(description='FinanceOS PATCH 10 - Otimização de estratégias')
    parser.add_argument('--strategy', default='multi_factor', choices=['score_top_n','momentum','dividend_yield','low_volatility','multi_factor'])
    parser.add_argument('--asset-class', default='all', choices=['all','equity','fii','etf','bdr','crypto','index','currency','commodity'])
    parser.add_argument('--start-date', default='2020-01-01')
    parser.add_argument('--end-date', default='2024-01-01')
    parser.add_argument('--initial-capital', type=float, default=10000.0)
    parser.add_argument('--top-n-values', default='5,10')
    parser.add_argument('--rebalance-values', default='monthly')
    parser.add_argument('--min-score-values', default='')
    parser.add_argument('--max-position-pct-values', default='')
    parser.add_argument('--transaction-cost-values', default='0.001')
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--walk-forward', action='store_true')
    return parser.parse_args()


def build_weight_sets(strategy: str):
    if strategy != 'multi_factor':
        return [{}]
    return [
        {'weight_return': 0.25, 'weight_risk': 0.20, 'weight_liquidity': 0.15, 'weight_dividend': 0.20, 'weight_trend': 0.20},
        {'weight_return': 0.35, 'weight_risk': 0.25, 'weight_liquidity': 0.15, 'weight_dividend': 0.10, 'weight_trend': 0.15},
        {'weight_return': 0.20, 'weight_risk': 0.20, 'weight_liquidity': 0.20, 'weight_dividend': 0.25, 'weight_trend': 0.15},
    ]


def main():
    args = parse_args()
    top_n_values = parse_values(args.top_n_values, int, [5, 10])
    rebalance_values = parse_values(args.rebalance_values, str, ['monthly'])
    min_score_values = parse_values(args.min_score_values, parse_float_or_none, [None]) or [None]
    max_pos_values = parse_values(args.max_position_pct_values, parse_float_or_none, [None]) or [None]
    tx_values = parse_values(args.transaction_cost_values, float, [0.001])
    weight_sets = build_weight_sets(args.strategy)

    if args.walk_forward:
        parameter_sets = []
        for top_n in top_n_values:
            for rebalance in rebalance_values:
                for min_score in min_score_values:
                    for max_pos in max_pos_values:
                        for tx_cost in tx_values:
                            for weights in weight_sets:
                                parameter_sets.append({
                                    'top_n': top_n,
                                    'rebalance_frequency': rebalance,
                                    'min_score': min_score,
                                    'max_position_pct': max_pos,
                                    'transaction_cost': tx_cost,
                                    **weights,
                                })
        optimizer = WalkForwardOptimizer()
        result = optimizer.run(args.strategy, args.asset_class, args.start_date, args.end_date, args.initial_capital, parameter_sets, limit=args.limit)
    else:
        optimizer = GridSearchOptimizer()
        result = optimizer.run(
            strategy=args.strategy,
            asset_class=args.asset_class,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.initial_capital,
            top_n_values=top_n_values,
            rebalance_values=rebalance_values,
            min_score_values=min_score_values,
            max_position_pct_values=max_pos_values,
            transaction_cost_values=tx_values,
            weight_sets=weight_sets,
            limit=args.limit,
        )
    print('\nOTIMIZAÇÃO FINALIZADA')
    print('=' * 80)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
