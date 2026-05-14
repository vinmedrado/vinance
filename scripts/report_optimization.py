import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.backtest.optimization.optimization_repository import OptimizationRepository


def pct(value):
    if value is None:
        return 'n/a'
    return f'{float(value) * 100:.2f}%'


def main():
    repo = OptimizationRepository()
    runs = repo.latest_runs(limit=5)
    print('\nRELATÓRIO DE OTIMIZAÇÃO - FinanceOS')
    print('=' * 100)
    if not runs:
        print('Nenhuma otimização encontrada. Rode: python scripts/run_optimization.py --strategy=multi_factor --limit=10')
        return
    print('Últimas execuções:')
    for run in runs:
        print(f"#{run['id']} | {run['strategy_name']} | {run['asset_class']} | {run['start_date']}→{run['end_date']} | {run['mode']} | {run['status']}")

    latest_run_id = runs[0]['id']
    print('\nMelhores resultados da última execução:')
    print('-' * 100)
    rows = repo.best_results(run_id=latest_run_id, limit=10)
    if not rows:
        print('Sem resultados persistidos para a última execução.')
        return
    for idx, row in enumerate(rows, start=1):
        params = json.loads(row['parameters_json'] or '{}')
        warnings = json.loads(row['warnings_json'] or '[]')
        print(f"{idx:02d}. score_robustez={row['score_robustez']} | retorno={pct(row['total_return'])} | anual={pct(row['annual_return'])} | DD={pct(row['max_drawdown'])} | Sharpe={row['sharpe_ratio']} | trades={row['total_trades']}")
        print(f"    params={params}")
        if warnings:
            print(f"    alertas={warnings}")


if __name__ == '__main__':
    main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
