import math
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Position:
    ticker: str
    quantity: float
    avg_price: float


class PortfolioManager:
    """Controle simples e determinístico de caixa/posições para backtests.

    HOTFIX 9.4:
    - garante caixa inicial = initial_capital;
    - sizing inteiro via floor(target_value / price);
    - bloqueia compra apenas quando realmente não há caixa/quantidade/preço válido;
    - mantém posições entre rebalanceamentos.
    """

    def __init__(self, initial_capital: float, transaction_cost: float = 0.001):
        self.initial_capital = float(initial_capital or 0.0)
        if self.initial_capital <= 0:
            raise ValueError('initial_capital deve ser maior que zero para executar backtest.')
        self.cash = float(self.initial_capital)
        self.transaction_cost = float(transaction_cost or 0.0)
        self.positions: Dict[str, Position] = {}
        self.trades: List[dict] = []
        self.last_reject_reason: Optional[dict] = None

    def position_value(self, ticker: str, price: float) -> float:
        pos = self.positions.get(ticker)
        return 0.0 if not pos else float(pos.quantity) * float(price)

    def preview_buy_to_value(self, ticker: str, price: float, target_value: float) -> dict:
        """Calcula ordem antes de executar.

        Regra do PATCH 9.4:
        target_value_per_asset = equity / selected_count
        quantity = floor(target_value / price)
        buy_value = quantity * price
        """
        cash_before = float(self.cash)
        price = float(price or 0.0)
        target_value = float(target_value or 0.0)
        result = {
            'ticker': ticker,
            'price': price,
            'target_value': target_value,
            'quantity': 0,
            'buy_value': 0.0,
            'transaction_cost': 0.0,
            'total_cost': 0.0,
            'cash_before': cash_before,
            'cash_after_estimated': cash_before,
            'can_execute': False,
            'reason': None,
        }
        if price <= 0:
            result['reason'] = 'preço inválido ou zero'
            return result
        if target_value <= 0:
            result['reason'] = 'valor alvo inválido ou zero'
            return result
        if cash_before <= 0:
            result['reason'] = 'caixa insuficiente: cash <= 0'
            return result

        quantity = math.floor(target_value / price)
        if quantity <= 0:
            result['reason'] = 'quantidade zero: target_value menor que preço unitário'
            return result

        buy_value = float(quantity) * price
        fee = buy_value * self.transaction_cost
        total_cost = buy_value + fee

        # Se o alvo cabia matematicamente mas a taxa fez ultrapassar o caixa, reduz quantidade.
        if total_cost > cash_before + 1e-9:
            affordable_qty = math.floor(cash_before / (price * (1.0 + self.transaction_cost)))
            if affordable_qty <= 0:
                result.update({
                    'quantity': 0,
                    'buy_value': 0.0,
                    'transaction_cost': 0.0,
                    'total_cost': 0.0,
                    'reason': 'caixa insuficiente para comprar 1 unidade incluindo taxa',
                })
                return result
            quantity = affordable_qty
            buy_value = float(quantity) * price
            fee = buy_value * self.transaction_cost
            total_cost = buy_value + fee

        result.update({
            'quantity': int(quantity),
            'buy_value': buy_value,
            'transaction_cost': fee,
            'total_cost': total_cost,
            'cash_after_estimated': cash_before - total_cost,
            'can_execute': total_cost <= cash_before + 1e-9 and quantity > 0,
            'reason': None if total_cost <= cash_before + 1e-9 else 'buy_value maior que cash disponível',
        })
        return result

    def buy_to_value(self, ticker: str, price: float, target_value: float, date: str) -> Optional[dict]:
        preview = self.preview_buy_to_value(ticker, price, target_value)
        self.last_reject_reason = None if preview['can_execute'] else preview
        if not preview['can_execute']:
            return None

        cash_before = float(self.cash)
        qty = float(preview['quantity'])
        gross = float(preview['buy_value'])
        cost = float(preview['transaction_cost'])
        total = float(preview['total_cost'])

        old = self.positions.get(ticker)
        if old:
            new_qty = old.quantity + qty
            avg = ((old.quantity * old.avg_price) + gross) / new_qty
            self.positions[ticker] = Position(ticker, new_qty, avg)
        else:
            self.positions[ticker] = Position(ticker, qty, float(price))

        self.cash = max(0.0, self.cash - total)
        trade = {
            'ticker': ticker,
            'action': 'buy',
            'date': date,
            'price': float(price),
            'quantity': qty,
            'gross_value': gross,
            'transaction_cost': cost,
            'net_value': total,
            'cash_before': cash_before,
            'cash_after': self.cash,
            'target_value': float(target_value or 0.0),
        }
        self.trades.append(trade)
        return trade

    def sell_quantity(self, ticker: str, price: float, quantity: float, date: str, target_value: float = 0.0, delta: float = 0.0) -> Optional[dict]:
        """Vende uma quantidade parcial ou total da posição.

        PATCH 9.5:
        - usado no rebalanceamento real quando current_value > target_value;
        - aumenta cash;
        - reduz posição mantendo o restante;
        - registra trade de venda com cash_before/cash_after.
        """
        pos = self.positions.get(ticker)
        price = float(price or 0.0)
        if not pos or price <= 0:
            self.last_reject_reason = {
                'ticker': ticker,
                'action': 'sell',
                'price': price,
                'quantity': quantity,
                'reason': 'posição inexistente ou preço inválido para venda',
            }
            return None

        qty = min(float(quantity or 0.0), float(pos.quantity))
        if qty <= 0:
            self.last_reject_reason = {
                'ticker': ticker,
                'action': 'sell',
                'price': price,
                'quantity': qty,
                'reason': 'quantidade de venda zero',
            }
            return None

        cash_before = float(self.cash)
        gross = qty * price
        cost = gross * self.transaction_cost
        net = gross - cost
        self.cash += net

        remaining_qty = float(pos.quantity) - qty
        if remaining_qty <= 1e-12:
            del self.positions[ticker]
        else:
            self.positions[ticker] = Position(ticker, remaining_qty, pos.avg_price)

        trade = {
            'ticker': ticker,
            'action': 'sell',
            'date': date,
            'price': price,
            'quantity': qty,
            'gross_value': gross,
            'transaction_cost': cost,
            'net_value': net,
            'cash_before': cash_before,
            'cash_after': self.cash,
            'target_value': float(target_value or 0.0),
            'delta': float(delta or 0.0),
        }
        self.trades.append(trade)
        self.last_reject_reason = None
        return trade

    def sell_all(self, ticker: str, price: float, date: str) -> Optional[dict]:
        pos = self.positions.get(ticker)
        if not pos or price <= 0:
            return None
        cash_before = float(self.cash)
        gross = pos.quantity * float(price)
        cost = gross * self.transaction_cost
        net = gross - cost
        self.cash += net
        del self.positions[ticker]
        trade = {
            'ticker': ticker,
            'action': 'sell',
            'date': date,
            'price': float(price),
            'quantity': pos.quantity,
            'gross_value': gross,
            'transaction_cost': cost,
            'net_value': net,
            'cash_before': cash_before,
            'cash_after': self.cash,
        }
        self.trades.append(trade)
        return trade

    def total_value(self, prices: Dict[str, float]) -> float:
        return float(self.cash) + self.positions_value(prices)

    def positions_value(self, prices: Dict[str, float]) -> float:
        total = 0.0
        for ticker, pos in self.positions.items():
            price = float(prices.get(ticker, pos.avg_price) or pos.avg_price)
            total += pos.quantity * price
        return total
