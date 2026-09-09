from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Any


ENGINE_VERSION = "financial-policy-v1"
RULES_VERSION = "financial-policy-rules-v1"
SUPPORTED_FINANCIAL_STATE_VERSION = "household-financial-state-v1"


@dataclass(frozen=True)
class PolicyRulesV1:
    """Prudential thresholds frozen for reproducible policy-v1 decisions.

    Percentages use the same 0..100 scale emitted by Financial State v1. These
    limits order financial priorities; they never select securities or forecast
    market returns.
    """

    minimum_policy_confidence: int = 50
    minimum_ready_confidence: int = 85
    debt_service_priority_pct: Decimal = Decimal("20.00")
    debt_service_block_pct: Decimal = Decimal("30.00")
    debt_to_income_warning_pct: Decimal = Decimal("50.00")
    known_high_cost_debt_apr_pct: Decimal = Decimal("15.00")
    near_term_debt_days: int = 90
    reserve_base_months: Decimal = Decimal("3.00")
    reserve_max_months: Decimal = Decimal("6.00")
    reserve_modifier_months: Decimal = Decimal("1.00")
    fixed_expense_pressure_pct: Decimal = Decimal("70.00")
    non_recurring_income_dependency_pct: Decimal = Decimal("20.00")
    urgent_goal_days: int = 90
    near_term_goal_days: int = 365
    goal_planning_month_days: int = 30

    def public_thresholds(self) -> dict[str, Any]:
        return asdict(self)


RULES = PolicyRulesV1()

RULE_CATALOG = MappingProxyType(
    {
        "FPV1-DATA-001": "O Financial State precisa ser da versão canônica suportada.",
        "FPV1-DATA-002": "Qualidade inconsistente ou insuficiente bloqueia a política.",
        "FPV1-DATA-003": "Confidence abaixo do piso prudencial bloqueia a política.",
        "FPV1-DATA-004": "Campos de decisão ausentes bloqueiam a política.",
        "FPV1-DATA-005": "Receitas ou despesas stale bloqueiam decisões novas.",
        "FPV1-DATA-006": "Moedas não comparáveis bloqueiam agregados sem conversão explícita.",
        "FPV1-DATA-007": "O contexto normalizado deve pertencer ao mesmo household do Financial State.",
        "FPV1-CASH-001": "Fluxo disponível não positivo prioriza recuperação de caixa.",
        "FPV1-CASH-002": "Deterioração observada para caixa não positivo reforça a recuperação.",
        "FPV1-DEBT-001": "Default explícito torna dívida prioridade crítica.",
        "FPV1-DEBT-002": "Taxa anual conhecida elevada torna dívida prioridade.",
        "FPV1-DEBT-003": "Serviço da dívida elevado torna dívida prioridade.",
        "FPV1-DEBT-004": "DTI elevado gera alerta, sem bloquear isoladamente.",
        "FPV1-DEBT-005": "Vencimento conhecido próximo ordena prioridade sem presumir default.",
        "FPV1-NET-001": "Patrimônio líquido negativo prioriza redução prudente de passivos.",
        "FPV1-RESERVE-001": "O alvo de reserva parte de um piso e recebe ajustes contextuais conhecidos.",
        "FPV1-RESERVE-002": "Reserva abaixo do alvo conhecido precede novos investimentos.",
        "FPV1-GOAL-001": "Objetivo ativo com funding gap conhecido e urgente ou HIGH recebe prioridade.",
        "FPV1-GOAL-002": "Funding mensal requerido usa somente gap, prazo e capacidade de poupança conhecidos.",
        "FPV1-READY-001": "Prontidão exige dados suficientes, caixa positivo e ausência de prioridades superiores.",
    }
)

POLICY_STATE_PRECEDENCE = (
    "DATA_BLOCKED",
    "CASHFLOW_RECOVERY",
    "DEBT_PRIORITY",
    "EMERGENCY_RESERVE_PRIORITY",
    "GOAL_PRIORITY",
    "INVESTMENT_READY",
    "BALANCED_BUILD",
)
CRITICAL_DECISION_FIELDS = (
    "recurring_monthly_income",
    "total_expenses",
    "disposable_income",
    "savings_capacity",
)
READINESS_CORE_FIELDS = (
    "investment_capacity",
    "total_assets",
    "total_liabilities",
    "net_worth",
    "emergency_reserve",
)
SUPPORTED_AGGREGATE_CURRENCIES = ("BRL",)

# Messages that identify information which, if supplied or corrected, can
# materially change the policy.  Keeping this catalogue versioned with the
# rules makes the API's ``missing_information`` output deterministic and
# auditable instead of relying on wording heuristics.
MISSING_INFORMATION_CODES = frozenset(
    {
        "POLICY_CONTEXT_MISSING",
        "FINANCIAL_STATE_FIELDS_MISSING",
        "DECISION_CORE_MISSING",
        "CURRENCY_MISSING",
        "READINESS_CORE_MISSING",
        "GOALS_NOT_DECLARED",
        "DEBT_RATE_UNKNOWN",
        "DEBT_DUE_DATE_UNKNOWN",
        "DEBT_SERVICE_CONTEXT_UNKNOWN",
        "FIXED_EXPENSE_SHARE_UNKNOWN",
        "GOAL_PROGRESS_UNKNOWN",
        "GOAL_DEADLINE_UNKNOWN",
        "GOAL_FUNDING_GAP_UNKNOWN",
        "EMPLOYMENT_STABILITY_NOT_MODELED",
        "DEPENDENTS_NOT_MODELED",
        "FINANCIAL_TREND_HISTORY_NOT_AVAILABLE",
    }
)

GOAL_PRIORITY_WEIGHTS = MappingProxyType({"HIGH": 3, "MEDIUM": 2, "LOW": 1})
GOAL_URGENCY_WEIGHTS = MappingProxyType(
    {"OVERDUE": 4, "URGENT": 3, "NEAR_TERM": 2, "UNSCHEDULED": 0}
)
DEBT_DUE_WEIGHTS = MappingProxyType(
    {"DATE_PASSED_STATUS_ACTIVE": 2, "DUE_SOON": 1, "OTHER": 0}
)

PRIORITY_ORDER = MappingProxyType(
    {
        "COMPLETE_CRITICAL_DATA": 0,
        "STABILIZE_CASH_FLOW": 10,
        "REDUCE_DEBT_BURDEN": 20,
        "BUILD_EMERGENCY_RESERVE": 30,
        "FUND_PRIORITY_GOAL": 40,
        "COMPLETE_READINESS_DATA": 45,
        "INVEST_SURPLUS_CAPITAL": 50,
    }
)
