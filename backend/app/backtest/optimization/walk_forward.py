from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..backtest_repository import BacktestRepository
from ..strategies.strategy_runner import StrategyBacktestRunner
from .optimization_metrics import robustness_score
from .optimization_repository import OptimizationRepository


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value[:10], '%Y-%m-%d')


def _fmt(value: datetime) -> str:
    return value.strftime('%Y-%m-%d')


def build_windows(start_date: str, end_date: str, train_days: int = 365, test_days: int = 180) -> List[Dict[str, str]]:
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    windows: List[Dict[str, str]] = []
    cursor = start
    while cursor + timedelta(days=train_days + 30) <= end:
        train_start = cursor
        train_end = min(cursor + timedelta(days=train_days), end)
        test_start = train_end + timedelta(days=1)
        test_end = min(test_start + timedelta(days=test_days), end)
        if test_start <= test_end:
            windows.append({
                'train_start': _fmt(train_start),
                'train_end': _fmt(train_end),
                'test_start': _fmt(test_start),
                'test_end': _fmt(test_end),
            })
        cursor = test_start
    return windows


class WalkForwardOptimizer:
    def __init__(self, opt_repository: Optional[OptimizationRepository] = None, backtest_repository: Optional[BacktestRepository] = None):
        self.opt_repository = opt_repository or OptimizationRepository()
        self.backtest_repository = backtest_repository or BacktestRepository()
        self.runner = StrategyBacktestRunner(self.backtest_repository)

    def run(self, strategy: str, asset_class: str, start_date: str, end_date: str, initial_capital: float, parameter_sets: List[Dict[str, Any]], limit: Optional[int] = None) -> Dict[str, Any]:
        windows = build_windows(start_date, end_date)
        if limit:
            parameter_sets = parameter_sets[: int(limit)]
        run_id = self.opt_repository.create_run(strategy, asset_class, start_date, end_date, 'walk_forward', {'parameter_sets': parameter_sets, 'windows': windows})
        all_results: List[Dict[str, Any]] = []
        try:
            for idx, window in enumerate(windows, start=1):
                train_results = []
                for params in parameter_sets:
                    train = self.runner.run(
                        strategy=strategy,
                        asset_class=asset_class,
                        start_date=window['train_start'],
                        end_date=window['train_end'],
                        initial_capital=initial_capital,
                        dry_run=True,
                        **params,
                    )
                    score = robustness_score(train.get('metrics', {}), total_assets=int(params.get('top_n', 0) or 0))
                    train_results.append((score, params, train))
                if not train_results:
                    continue
                train_results.sort(key=lambda x: x[0], reverse=True)
                _, best_params, _ = train_results[0]
                test = self.runner.run(
                    strategy=strategy,
                    asset_class=asset_class,
                    start_date=window['test_start'],
                    end_date=window['test_end'],
                    initial_capital=initial_capital,
                    dry_run=True,
                    **best_params,
                )
                metrics = test.get('metrics', {})
                score = robustness_score(metrics, [metrics.get('total_return')], total_assets=int(best_params.get('top_n', 0) or 0))
                row = {
                    'strategy_name': strategy,
                    'asset_class': asset_class,
                    'window_name': f'WF-{idx}',
                    'train_start': window['train_start'],
                    'train_end': window['train_end'],
                    'test_start': window['test_start'],
                    'test_end': window['test_end'],
                    'parameters': best_params,
                    'metrics': metrics,
                    'score_robustez': score,
                    'warnings': ['walk-forward: parâmetros escolhidos no treino e avaliados fora da amostra'],
                }
                self.opt_repository.insert_result(run_id, row)
                all_results.append(row)
            self.opt_repository.finish_run(run_id, 'success')
        except Exception as exc:
            self.opt_repository.finish_run(run_id, 'failed', str(exc))
            raise
        return {'optimization_run_id': run_id, 'windows': len(windows), 'results': all_results}
