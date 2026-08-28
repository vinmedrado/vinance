from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Position:
    symbol: str
    quantity: float
    average_price: float


@dataclass
class PortfolioState:
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)

    def equity(self, prices: dict[str, float]) -> float:
        return self.cash + sum(
            position.quantity * prices.get(symbol, position.average_price)
            for symbol, position in self.positions.items()
        )
