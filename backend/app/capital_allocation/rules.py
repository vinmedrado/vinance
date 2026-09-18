from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Any


ENGINE_VERSION = "capital-allocation-v1"
RULES_VERSION = "capital-allocation-rules-v1"
SUPPORTED_FINANCIAL_STATE_VERSION = "household-financial-state-v1"
SUPPORTED_FINANCIAL_POLICY_VERSION = "financial-policy-v1"
SUPPORTED_POLICY_RULES_VERSION = "financial-policy-rules-v1"


@dataclass(frozen=True)
class CapitalAllocationRulesV1:
    """Operational invariants for allocation-v1, not a universal budget split."""

    allocation_period: str = "MONTHLY"
    settlement_currency: str = "BRL"
    money_quantum: Decimal = Decimal("0.01")
    rounding_mode: str = "ROUND_DOWN"
    speculative_capital_amount: Decimal = Decimal("0.00")

    def public_rules(self) -> dict[str, Any]:
        return asdict(self)


RULES = CapitalAllocationRulesV1()

RULE_CATALOG = MappingProxyType(
    {
        "CAV1-DATA-001": "Financial State e Financial Policy devem usar versões canônicas compatíveis.",
        "CAV1-DATA-002": "State, Policy, household e snapshots devem formar uma cadeia consistente.",
        "CAV1-DATA-003": "Bloqueios de dados da Policy impedem alocação monetária inventada.",
        "CAV1-DATA-004": "Valores sem conversão monetária confiável não podem ser agregados.",
        "CAV1-CAPITAL-001": "Capital alocável mensal deriva somente da investment capacity conhecida.",
        "CAV1-CAPITAL-002": "Patrimônio existente não é tratado como caixa para novas alocações.",
        "CAV1-ORDER-001": "A ordem das alocações segue os ranks produzidos pela Financial Policy.",
        "CAV1-CASH-001": "Recuperação de fluxo precede qualquer bucket de investimento.",
        "CAV1-DEBT-001": "Redução adicional de dívida usa somente saldos conhecidos e a ordem da Policy.",
        "CAV1-RESERVE-001": "A reserva usa exclusivamente o gap calculado pela Financial Policy.",
        "CAV1-GOAL-001": "Goals usam funding periódico conhecido ou, sem prazo, somente o gap conhecido.",
        "CAV1-OWN-001": (
            "Prioridade PERSONAL só consome capacidade do mesmo usuário; prioridade HOUSEHOLD "
            "só usa residual compartilhado comprovável. Em household de um membro, ambos os "
            "escopos reconciliam o mesmo pool sem transferência entre pessoas. Em household "
            "multimembro, capacidades pessoais superiores ao consolidado bloqueiam a decisão."
        ),
        "CAV1-INVEST-001": "Capital residual só vira investment bucket quando a Policy permite.",
        "CAV1-PROTECT-001": "Capital especulativo permanece explicitamente zero nesta versão.",
        "CAV1-CONSERVE-001": "Alocações não negativas nunca podem exceder o capital alocável.",
        "CAV1-ROUND-001": "Valores monetários usam Decimal, centavos e arredondamento conservador para baixo.",
    }
)

SUPPORTED_POLICY_STATES = frozenset(
    {
        "DATA_BLOCKED",
        "CASHFLOW_RECOVERY",
        "DEBT_PRIORITY",
        "EMERGENCY_RESERVE_PRIORITY",
        "GOAL_PRIORITY",
        "BALANCED_BUILD",
        "INVESTMENT_READY",
    }
)
SUPPORTED_INVESTMENT_READINESS = frozenset({"BLOCKED", "LIMITED", "READY"})

INFORMATIONAL_PRIORITY_CODES = frozenset(
    {"COMPLETE_CRITICAL_DATA", "COMPLETE_READINESS_DATA"}
)
MONETARY_PRIORITY_CODES = frozenset(
    {
        "STABILIZE_CASH_FLOW",
        "REDUCE_DEBT_BURDEN",
        "BUILD_EMERGENCY_RESERVE",
        "FUND_PRIORITY_GOAL",
    }
)
INVESTMENT_PRIORITY_CODE = "INVEST_SURPLUS_CAPITAL"

BUCKET_BY_PRIORITY = MappingProxyType(
    {
        "STABILIZE_CASH_FLOW": "PROTECTED_CAPITAL",
        "REDUCE_DEBT_BURDEN": "PROTECTED_CAPITAL",
        "BUILD_EMERGENCY_RESERVE": "PROTECTED_CAPITAL",
        "FUND_PRIORITY_GOAL": "GOAL_CAPITAL",
        "INVEST_SURPLUS_CAPITAL": "INVESTMENT_CAPITAL",
    }
)
