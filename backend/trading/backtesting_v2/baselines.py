from __future__ import annotations

import random
from typing import Any

from backend.trading.prediction_engine.decision import BUY_CANDIDATE
from backend.trading.prediction_engine.models import PredictionResult


def baseline_comparison(
    *,
    initial_capital: float,
    final_capital: float,
    first_close: float,
    last_close: float,
    predictions: list[PredictionResult],
    seed: int,
) -> dict[str, Any]:
    buy_count = sum(1 for item in predictions if item.decision == BUY_CANDIDATE)
    rng = random.Random(seed)
    random_return = sum(rng.choice((-0.001, 0.001)) for _ in range(buy_count))
    random_final = initial_capital * (1 + random_return)
    buy_hold_final = initial_capital * (last_close / first_close) if first_close else initial_capital
    return {
        "buy_and_hold": {"final_capital": buy_hold_final, "total_return": buy_hold_final / initial_capital - 1},
        "always_hold": {"final_capital": initial_capital, "total_return": 0.0},
        "random_same_signal_count": {
            "final_capital": random_final,
            "total_return": random_final / initial_capital - 1,
            "number_of_trades": buy_count,
        },
        "majority_class_hold": {"final_capital": initial_capital, "total_return": 0.0},
        "model_without_confidence_filter": {"final_capital": final_capital, "total_return": final_capital / initial_capital - 1},
    }
