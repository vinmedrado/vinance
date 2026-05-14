from collections import defaultdict, deque
from math import sqrt
from typing import Deque, Dict, List, Tuple

TRADING_DAYS = 252


def _returns(values: List[float]) -> List[float]:
    out = []
    for a, b in zip(values, values[1:]):
        if a and a > 0:
            out.append((b / a) - 1)
    return out


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return (sum((x - mean) ** 2 for x in values) / (len(values) - 1)) ** 0.5


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_closed_trade_stats(trades: List[Dict]) -> Dict:
    """Calcula estatísticas de trades fechados usando pareamento FIFO buy -> sell.

    Regra do PATCH 10.3:
    - compra isolada NÃO entra no win rate;
    - posição aberta NÃO entra no win rate;
    - cada venda é comparada contra o custo real da quantidade vendida;
    - custos de transação são considerados via net_value:
        buy_value = valor bruto + custo da compra
        sell_value = valor bruto - custo da venda
    """
    lots_by_ticker: Dict[str, Deque[Tuple[float, float]]] = defaultdict(deque)
    closed_trades: List[Dict] = []
    unmatched_sells = 0

    ordered = sorted(
        trades or [],
        key=lambda t: (str(t.get('date') or ''), int(t.get('id') or t.get('sequence') or 0)),
    )

    for trade in ordered:
        ticker = str(trade.get('ticker') or '').upper().strip()
        action = str(trade.get('action') or '').lower().strip()
        qty = abs(_safe_float(trade.get('quantity')))
        if not ticker or qty <= 0:
            continue

        gross = abs(_safe_float(trade.get('gross_value')))
        fee = abs(_safe_float(trade.get('transaction_cost')))
        net = abs(_safe_float(trade.get('net_value')))

        if action == 'buy':
            # Compatível com versões antigas: se net_value não vier preenchido,
            # usa bruto + taxa como custo total de entrada.
            buy_total_cost = net if net > 0 else gross + fee
            unit_cost = buy_total_cost / qty if qty > 0 else 0.0
            if unit_cost > 0:
                lots_by_ticker[ticker].append([qty, unit_cost])
            continue

        if action != 'sell':
            continue

        sell_total_value = net if net > 0 else max(0.0, gross - fee)
        sell_unit_value = sell_total_value / qty if qty > 0 else 0.0
        remaining_to_close = qty
        matched_qty = 0.0
        buy_value = 0.0

        while remaining_to_close > 1e-12 and lots_by_ticker[ticker]:
            lot_qty, lot_unit_cost = lots_by_ticker[ticker][0]
            close_qty = min(remaining_to_close, lot_qty)
            matched_qty += close_qty
            buy_value += close_qty * lot_unit_cost
            remaining_to_close -= close_qty
            lot_qty -= close_qty
            if lot_qty <= 1e-12:
                lots_by_ticker[ticker].popleft()
            else:
                lots_by_ticker[ticker][0][0] = lot_qty

        if matched_qty <= 1e-12:
            unmatched_sells += 1
            continue

        # Se a venda foi maior que a posição pareada, avalia somente a fração pareada.
        matched_sell_value = sell_unit_value * matched_qty
        pnl = matched_sell_value - buy_value
        closed_trades.append({
            'ticker': ticker,
            'date': trade.get('date'),
            'quantity': matched_qty,
            'buy_value': buy_value,
            'sell_value': matched_sell_value,
            'pnl': pnl,
            'return_pct': (pnl / buy_value) if buy_value > 0 else 0.0,
            'is_win': matched_sell_value > buy_value,
        })

    total_closed = len(closed_trades)
    winning = sum(1 for t in closed_trades if t['is_win'])
    losing = total_closed - winning
    total_pnl = sum(t['pnl'] for t in closed_trades)
    avg_pnl = total_pnl / total_closed if total_closed else 0.0
    win_rate = winning / total_closed if total_closed else 0.0
    open_lots = sum(len(lots) for lots in lots_by_ticker.values())
    open_quantity = sum(sum(float(lot[0]) for lot in lots) for lots in lots_by_ticker.values())

    return {
        'win_rate': win_rate,
        'closed_trades': total_closed,
        'profitable_trades': winning,
        'losing_trades': losing,
        'avg_pnl_per_trade': avg_pnl,
        'total_closed_pnl': total_pnl,
        'unmatched_sells': unmatched_sells,
        'open_lots': open_lots,
        'open_quantity': open_quantity,
        'closed_trade_details': closed_trades[:100],
    }


def calculate_backtest_metrics(equity_curve: List[Dict], trades: List[Dict], initial_capital: float, risk_free_rate: float = 0.0) -> Dict:
    if not equity_curve:
        closed_stats = calculate_closed_trade_stats(trades)
        return {
            'total_return': 0,
            'annual_return': 0,
            'volatility': 0,
            'max_drawdown': 0,
            'sharpe_ratio': 0,
            'win_rate': closed_stats['win_rate'],
            'total_trades': len(trades or []),
            'turnover': 0,
            **closed_stats,
        }

    values = [float(x['equity_value']) for x in equity_curve]
    final_value = values[-1]
    total_return = (final_value / initial_capital) - 1 if initial_capital else 0
    days = max(1, len(values))
    annual_return = ((1 + total_return) ** (TRADING_DAYS / days)) - 1 if total_return > -1 else -1
    rets = _returns(values)
    daily_vol = _std(rets)
    volatility = daily_vol * sqrt(TRADING_DAYS)
    daily_rf = risk_free_rate / TRADING_DAYS
    excess = [(r - daily_rf) for r in rets]
    sharpe = ((sum(excess) / len(excess)) / daily_vol) * sqrt(TRADING_DAYS) if rets and daily_vol > 0 else 0

    peak = values[0]
    max_dd = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_dd = min(max_dd, (value / peak) - 1)

    closed_stats = calculate_closed_trade_stats(trades)
    turnover = sum(abs(float(t.get('gross_value', 0) or 0)) for t in trades or []) / initial_capital if initial_capital else 0

    return {
        'total_return': total_return,
        'annual_return': annual_return,
        'volatility': volatility,
        'max_drawdown': max_dd,
        'sharpe_ratio': sharpe,
        'win_rate': closed_stats['win_rate'],
        'total_trades': len(trades or []),
        'turnover': turnover,
        'final_value': final_value,
        **closed_stats,
    }
