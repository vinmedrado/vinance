import itertools
from typing import Any, Dict, Iterable, List, Optional

from ..backtest_repository import BacktestRepository
from ..strategies.strategy_runner import StrategyBacktestRunner
from .optimization_metrics import robustness_score
from .optimization_repository import OptimizationRepository


def parse_values(raw: Optional[str], cast=str, default: Optional[List[Any]] = None) -> List[Any]:
    if raw is None or str(raw).strip() == '':
        return default or []
    return [cast(x.strip()) for x in str(raw).split(',') if x.strip()]


class GridSearchOptimizer:
    def __init__(self, opt_repository: Optional[OptimizationRepository] = None, backtest_repository: Optional[BacktestRepository] = None):
        self.opt_repository = opt_repository or OptimizationRepository()
        self.backtest_repository = backtest_repository or BacktestRepository()
        self.runner = StrategyBacktestRunner(self.backtest_repository)

    def run(
        self,
        strategy: str,
        asset_class: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 10000.0,
        top_n_values: Iterable[int] = (5, 10),
        rebalance_values: Iterable[str] = ('monthly',),
        min_score_values: Iterable[Optional[float]] = (None,),
        max_position_pct_values: Iterable[Optional[float]] = (None,),
        transaction_cost_values: Iterable[float] = (0.001,),
        weight_sets: Optional[List[Dict[str, float]]] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        weight_sets = weight_sets or [{}]
        params_grid = list(itertools.product(top_n_values, rebalance_values, min_score_values, max_position_pct_values, transaction_cost_values, weight_sets))
        if limit:
            params_grid = params_grid[: int(limit)]

        run_id = self.opt_repository.create_run(strategy, asset_class, start_date, end_date, 'grid_search', {
            'top_n_values': list(top_n_values),
            'rebalance_values': list(rebalance_values),
            'min_score_values': list(min_score_values),
            'max_position_pct_values': list(max_position_pct_values),
            'transaction_cost_values': list(transaction_cost_values),
            'weight_sets': weight_sets,
            'limit': limit,
        })
        results: List[Dict[str, Any]] = []
        try:
            for top_n, rebalance, min_score, max_pos, tx_cost, weights in params_grid:
                params = {
                    'top_n': int(top_n),
                    'rebalance_frequency': rebalance,
                    'min_score': min_score,
                    'max_position_pct': max_pos,
                    'transaction_cost': float(tx_cost),
                    **weights,
                }
                warnings: List[str] = []
                result = self.runner.run(
                    strategy=strategy,
                    asset_class=asset_class,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=initial_capital,
                    top_n=int(top_n),
                    rebalance_frequency=rebalance,
                    min_score=min_score,
                    max_position_pct=max_pos,
                    transaction_cost=float(tx_cost),
                    dry_run=True,
                    **weights,
                )
                metrics = result.get('metrics', {})
                if int(metrics.get('total_trades') or 0) < 5:
                    warnings.append('Poucos trades: risco de overfitting/resultado pouco representativo')
                score = robustness_score(metrics, total_assets=int(top_n))
                row = {
                    'strategy_name': strategy,
                    'asset_class': asset_class,
                    'parameters': params,
                    'metrics': metrics,
                    'score_robustez': score,
                    'warnings': warnings,
                }
                self.opt_repository.insert_result(run_id, row)
                results.append(row)
            self.opt_repository.finish_run(run_id, 'success')
        except Exception as exc:
            self.opt_repository.finish_run(run_id, 'failed', str(exc))
            raise

        results.sort(key=lambda r: r.get('score_robustez') or 0, reverse=True)
        return {'optimization_run_id': run_id, 'tested': len(results), 'best': results[:5]}
