from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any


ENGINE_VERSION = "action-plan-v1"
RULES_VERSION = "action-plan-rules-v1"
MONEY_QUANTUM = Decimal("0.01")


@dataclass(frozen=True)
class ActionPlanRules:
    engine_version: str = ENGINE_VERSION
    rules_version: str = RULES_VERSION
    period: str = "MONTHLY"
    speculative_capital: Decimal = Decimal("0.00")
    trading_dispatch: bool = False
    preserve_upstream_rounding: bool = True
    rule_ids: tuple[str, ...] = (
        "APV1-CHAIN-001",
        "APV1-INFORMATION-001",
        "APV1-FINANCIAL-001",
        "APV1-INVESTMENT-001",
        "APV1-HOLD-001",
        "APV1-OWNERSHIP-001",
        "APV1-CONSERVATION-001",
        "APV1-DETERMINISM-001",
        "APV1-TRADING-001",
    )

    def payload(self) -> dict[str, Any]:
        return asdict(self)


RULES = ActionPlanRules()
