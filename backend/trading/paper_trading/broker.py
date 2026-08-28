from __future__ import annotations

from datetime import datetime, timezone

from ..execution.base import ExecutionBroker, OrderRequest, OrderResult


class PaperBroker(ExecutionBroker):
    def __init__(self, fee_bps: float = 10.0, slippage_bps: float = 5.0) -> None:
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps

    def execute(self, order: OrderRequest, market_price: float) -> OrderResult:
        if order.quantity <= 0 or market_price <= 0:
            return OrderResult(False, None, None, "Quantidade ou preço inválido.")
        direction = 1 if order.side.upper() == "BUY" else -1
        execution_price = market_price * (1 + direction * self.slippage_bps / 10_000)
        return OrderResult(True, execution_price, datetime.now(timezone.utc), "Ordem simulada executada.")
