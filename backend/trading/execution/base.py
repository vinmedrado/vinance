from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    quantity: float


@dataclass(frozen=True)
class OrderResult:
    accepted: bool
    execution_price: float | None
    executed_at: datetime | None
    message: str


class ExecutionBroker(ABC):
    @abstractmethod
    def execute(self, order: OrderRequest, market_price: float) -> OrderResult:
        raise NotImplementedError
