from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


ENGINE_VERSION = "fixed-income-v1"
RULES_VERSION = "fixed-income-rules-v1"
FRESHNESS_DAYS = 5
SETTLEMENT_CURRENCY = "BRL"
MONEY_QUANTUM = Decimal("0.01")
MONEY_ROUNDING = ROUND_DOWN
DURATION_SENSITIVE_TYPES = frozenset(
    {
        "TREASURY_PREFIXED",
        "TREASURY_IPCA",
        "TREASURY_RENDA_PLUS",
        "TREASURY_EDUCA_PLUS",
        "TREASURY_OTHER",
    }
)
LIQUID_TYPES = frozenset({"DAILY_REPURCHASE", "DAILY_LIQUIDITY"})


@dataclass(frozen=True)
class FixedIncomeRules:
    freshness_days: int = FRESHNESS_DAYS
    settlement_currency: str = SETTLEMENT_CURRENCY
    money_quantum: Decimal = MONEY_QUANTUM
    rounding_mode: str = "ROUND_DOWN"


RULES = FixedIncomeRules()


RULE_CATALOG = {
    "FIV1-DATA-001": "Somente produtos ativos, atuais e com fatos críticos conhecidos podem avançar.",
    "FIV1-CURRENCY-001": "A moeda do produto precisa ser compatível sem FX inventado.",
    "FIV1-BUDGET-001": "O aporte mínimo conhecido deve caber no budget autorizado.",
    "FIV1-HORIZON-001": "Vencimento e liquidez devem ser compatíveis com o horizonte conhecido.",
    "FIV1-PROFILE-001": "Adequação considera o perfil explícito sem criar um perfil paralelo.",
    "FIV1-RANK-001": "Ranking deriva de adequação, não da maior taxa nominal.",
}
