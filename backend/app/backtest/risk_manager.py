from typing import Dict

class RiskManager:
    def __init__(self, max_position_pct: float = 0.15, min_price: float = 0.01, cash_buffer_pct: float = 0.10):
        self.max_position_pct = float(max_position_pct)
        self.min_price = float(min_price)
        self.cash_buffer_pct = max(0.0, min(float(cash_buffer_pct), 0.95))

    def is_price_valid(self, price: float) -> bool:
        return price is not None and price >= self.min_price

    def target_value(self, equity: float, selected_count: int) -> float:
        if selected_count <= 0:
            return 0.0
        investable_equity = equity * (1.0 - self.cash_buffer_pct)
        equal_weight_value = investable_equity / selected_count
        max_position_value = equity * self.max_position_pct
        return min(equal_weight_value, max_position_value)

    def allocation_pct(self, position_value: float, equity: float) -> float:
        if not equity:
            return 0.0
        return float(position_value) / float(equity)
