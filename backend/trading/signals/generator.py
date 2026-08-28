from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    side: str
    probability: float
    reason: str


def generate_signal(probability_up: float, buy_threshold: float = 0.62, sell_threshold: float = 0.38) -> Signal:
    if probability_up >= buy_threshold:
        return Signal("BUY", probability_up, "Probabilidade acima do limite de compra.")
    if probability_up <= sell_threshold:
        return Signal("SELL", 1 - probability_up, "Probabilidade abaixo do limite de venda.")
    return Signal("HOLD", max(probability_up, 1 - probability_up), "Probabilidade insuficiente.")
