from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

VALID_RISK_PROFILES = {"conservative", "moderate", "aggressive"}


@dataclass(frozen=True)
class FinancialConstraints:
    financial_score: int
    has_debt_default: bool = False
    emergency_reserve_months: Decimal | None = None
    emergency_reserve_priority: bool = False
    high_risk_allowed: bool = True


@dataclass
class RiskAdjustmentResult:
    risk_profile: str
    high_risk_allowed: bool
    crypto_allowed: bool
    actions_reduced: bool
    emergency_reserve_priority: bool
    warnings: list[str] = field(default_factory=list)


def normalize_risk_profile(risk_profile: str | None) -> str:
    value = (risk_profile or "conservative").strip().lower()
    return value if value in VALID_RISK_PROFILES else "conservative"


def can_recommend_high_risk(*, financial_score: int, has_debt_default: bool = False, high_risk_allowed: bool = True) -> bool:
    if financial_score < 40:
        return False
    if has_debt_default:
        return False
    return bool(high_risk_allowed)


def apply_financial_constraints(
    *,
    risk_profile: str | None,
    financial_score: int,
    has_debt_default: bool = False,
    emergency_reserve_months: Decimal | int | float | None = None,
    emergency_reserve_priority: bool = False,
    high_risk_allowed: bool = True,
) -> RiskAdjustmentResult:
    normalized = normalize_risk_profile(risk_profile)
    warnings: list[str] = []
    # Ausência de medição não equivale a uma reserva conhecida de zero meses.
    reserve_months = None if emergency_reserve_months is None else Decimal(str(emergency_reserve_months))
    reserve_priority = bool(
        emergency_reserve_priority
        or (reserve_months is not None and reserve_months < Decimal("3"))
    )
    crypto_allowed = True
    actions_reduced = False

    if (risk_profile or "").strip().lower() not in VALID_RISK_PROFILES:
        warnings.append("Perfil de risco inválido ajustado para conservative.")

    allowed_high_risk = can_recommend_high_risk(
        financial_score=financial_score,
        has_debt_default=has_debt_default,
        high_risk_allowed=high_risk_allowed,
    )

    if financial_score < 40:
        if normalized == "aggressive":
            normalized = "conservative"
        crypto_allowed = False
        actions_reduced = True
        warnings.append("Score financeiro abaixo de 40 bloqueia risco alto, cripto e reduz exposição a ações.")

    if has_debt_default:
        crypto_allowed = False
        actions_reduced = True
        warnings.append("Inadimplência informada bloqueia cripto e reduz ações.")

    if reserve_priority:
        warnings.append("Reserva de emergência abaixo de 3 meses ou marcada como prioridade aumenta renda fixa.")

    if not high_risk_allowed:
        crypto_allowed = False
        actions_reduced = True
        warnings.append("Preferência high_risk_allowed=false bloqueia cripto e reduz ações.")

    return RiskAdjustmentResult(
        risk_profile=normalized,
        high_risk_allowed=allowed_high_risk,
        crypto_allowed=crypto_allowed and allowed_high_risk,
        actions_reduced=actions_reduced,
        emergency_reserve_priority=reserve_priority,
        warnings=warnings,
    )


def explain_risk_adjustments(result: RiskAdjustmentResult) -> list[str]:
    explanations = list(result.warnings)
    if not explanations:
        explanations.append("Nenhum ajuste de risco aplicado além da normalização do perfil.")
    return explanations
