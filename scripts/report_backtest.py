import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.backtest.backtest_repository import BacktestRepository
from backend.app.backtest.metrics import calculate_closed_trade_stats


def fmt_pct(value):
    return f'{(value or 0) * 100:.2f}%'


def fmt_money(value):
    return f'{(value or 0):.2f}'


def load_metrics_json(metrics_row):
    if not metrics_row:
        return {}
    raw = metrics_row['metrics_json'] if 'metrics_json' in metrics_row.keys() else None
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def main():
    repo = BacktestRepository()
    runs = repo.latest_runs(10)
    print('\nRELATÓRIO DE BACKTESTS')
    print('=' * 80)
    if not runs:
        print('Nenhum backtest encontrado.')
        return

    for run in runs:
        metrics = repo.conn.execute('SELECT * FROM backtest_metrics WHERE backtest_id=?', (run['id'],)).fetchone()
        trade_rows = repo.conn.execute('SELECT * FROM backtest_trades WHERE backtest_id=? ORDER BY date, id', (run['id'],)).fetchall()
        trades = len(trade_rows)
        best = repo.conn.execute('SELECT ticker, COUNT(*) AS n FROM backtest_trades WHERE backtest_id=? GROUP BY ticker ORDER BY n DESC LIMIT 5', (run['id'],)).fetchall()
        closed_stats = calculate_closed_trade_stats([dict(r) for r in trade_rows])
        metrics_payload = load_metrics_json(metrics)

        # PATCH 10.3: se o backtest antigo ainda estiver com win_rate errado salvo,
        # o relatório exibe o cálculo corrigido com base nos trades reais.
        corrected_win_rate = closed_stats.get('win_rate', 0.0)
        profitable_trades = closed_stats.get('profitable_trades', 0)
        losing_trades = closed_stats.get('losing_trades', 0)
        closed_trades = closed_stats.get('closed_trades', 0)
        avg_pnl = closed_stats.get('avg_pnl_per_trade', 0.0)

        print(f"\n#{run['id']} | {run['strategy_name']} | {run['asset_class'] or 'all'} | {run['start_date']} → {run['end_date']} | status={run['status']}")
        print(f"Capital inicial: {run['initial_capital']:.2f} | Top N: {run['top_n']} | Rebalance: {run['rebalance_frequency']} | Trades: {trades}")
        if metrics:
            print(f"Retorno total: {fmt_pct(metrics['total_return'])} | Retorno anual: {fmt_pct(metrics['annual_return'])} | DD máx: {fmt_pct(metrics['max_drawdown'])} | Sharpe: {(metrics['sharpe_ratio'] or 0):.2f}")
            print(f"Win rate corrigido: {fmt_pct(corrected_win_rate)} | Trades fechados: {closed_trades} | Positivos: {profitable_trades} | Negativos: {losing_trades} | PnL médio/trade: {fmt_money(avg_pnl)}")
            print(f"Turnover: {(metrics['turnover'] or 0):.2f}")
            if metrics_payload and metrics_payload.get('win_rate') != corrected_win_rate:
                print('Obs.: win rate exibido recalculado por pares buy→sell com custos. Backtests antigos podem ter valor salvo anterior no banco.')
        if best:
            print('Ativos mais negociados: ' + ', '.join([f"{b['ticker']}({b['n']})" for b in best]))


if __name__ == '__main__':
    main()
