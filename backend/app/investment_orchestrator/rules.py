from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


ENGINE_VERSION = "investment-orchestrator-v1"
RULES_VERSION = "investment-orchestrator-rules-v1"
MONEY_QUANTUM = Decimal("0.01")
MONEY_ROUNDING = ROUND_DOWN
SETTLEMENT_CURRENCY = "BRL"
MARKET_FRESHNESS_DAYS = 7
CONCENTRATION_THRESHOLD_PCT = Decimal("50.00")
SUPPORTED_MARKETS = ("ACOES", "FII", "ETF", "BDR")
UNSUPPORTED_CLASSES = ("FIXED_INCOME", "CRYPTO")
VALID_STATUSES = {
    "BLOCKED",
    "LIMITED",
    "ACTIVE",
    "NO_SUITABLE_OPPORTUNITY",
}
PROFILE_ORDER = {"CONSERVATIVE": 0, "MODERATE": 1, "AGGRESSIVE": 2}


@dataclass(frozen=True)
class InvestmentOrchestratorRules:
    settlement_currency: str = SETTLEMENT_CURRENCY
    money_quantum: Decimal = MONEY_QUANTUM
    rounding_mode: str = "ROUND_DOWN"
    market_freshness_days: int = MARKET_FRESHNESS_DAYS
    concentration_threshold_pct: Decimal = CONCENTRATION_THRESHOLD_PCT
    speculative_capital: Decimal = Decimal("0.00")


RULES = InvestmentOrchestratorRules()


RULE_CATALOG = {
    "IOV1-CHAIN-001": "State, Policy e Allocation formam uma cadeia canônica íntegra.",
    "IOV1-GATE-001": "Somente investment bucket positivo e readiness compatível liberam avaliação.",
    "IOV1-PROFILE-001": "Perfil explícito é obrigatório; nenhum perfil padrão é inventado.",
    "IOV1-PORTFOLIO-001": "Carteira ausente permanece desconhecida e concentração conhecida é respeitada.",
    "IOV1-MARKET-001": "Scores exigem preço, fonte, data fresca e guardrail correspondente.",
    "IOV1-CLASS-001": "Elegibilidade deriva de perfil, risco, dados e concentração.",
    "IOV1-ALLOCATE-001": "Capital por classe deriva da força relativa das oportunidades elegíveis.",
    "IOV1-GUARDRAIL-001": "BLOCKED nunca compra; WARNING aguarda; APPROVED pode ser candidato.",
    "IOV1-BUDGET-001": "Budget Advisor fornece alternativas; uma por classe compromete capital.",
    "IOV1-NOOP-001": "Capital autorizado pode permanecer integralmente em caixa.",
    "IOV1-CONSERVE-001": "Sugestões e alocações nunca excedem o investment bucket.",
    "IOV1-ROUND-001": "Valores usam Decimal, centavos e ROUND_DOWN.",
    "IOV1-TRADING-001": "Capital especulativo e dispatch para Trading permanecem zero.",
}
