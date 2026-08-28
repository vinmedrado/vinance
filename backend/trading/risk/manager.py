from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskDecision:
    approved: bool
    position_value: float
    reason: str


class RiskManager:
    def __init__(self, max_position_pct: float = 0.05, max_daily_loss_pct: float = 0.02) -> None:
        self.max_position_pct = max_position_pct
        self.max_daily_loss_pct = max_daily_loss_pct

    def evaluate(self, equity: float, daily_pnl: float, requested_value: float) -> RiskDecision:
        if equity <= 0:
            return RiskDecision(False, 0.0, "Patrimônio inválido.")
        if daily_pnl <= -(equity * self.max_daily_loss_pct):
            return RiskDecision(False, 0.0, "Limite de perda diária atingido.")
        allowed = min(requested_value, equity * self.max_position_pct)
        return RiskDecision(allowed > 0, allowed, "Aprovado dentro do limite de exposição.")
