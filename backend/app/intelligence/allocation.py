from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from backend.app.intelligence.risk_rules import apply_financial_constraints

BASE_ALLOCATIONS: dict[str, dict[str, Decimal]] = {
    "conservative": {"renda_fixa": Decimal("40"), "fii": Decimal("30"), "acoes": Decimal("20"), "etf": Decimal("10"), "cripto": Decimal("0")},
    "moderate": {"renda_fixa": Decimal("25"), "fii": Decimal("25"), "acoes": Decimal("25"), "etf": Decimal("15"), "cripto": Decimal("10")},
    "aggressive": {"renda_fixa": Decimal("10"), "fii": Decimal("20"), "acoes": Decimal("30"), "etf": Decimal("20"), "cripto": Decimal("20")},
}
ORDER = ["renda_fixa", "fii", "acoes", "etf", "cripto"]


def _normalize_to_100(weights: dict[str, Decimal]) -> dict[str, Decimal]:
    cleaned = {key: max(Decimal("0"), Decimal(str(weights.get(key, 0)))) for key in ORDER}
    total = sum(cleaned.values())
    if total <= 0:
        cleaned = dict(BASE_ALLOCATIONS["conservative"])
        total = Decimal("100")
    normalized = {key: (value * Decimal("100") / total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) for key, value in cleaned.items()}
    diff = Decimal("100.00") - sum(normalized.values())
    normalized["renda_fixa"] += diff
    return normalized


def calculate_allocation(
    *,
    investment_capacity: Decimal | int | float,
    risk_profile: str | None,
    financial_score: int,
    emergency_reserve_priority: bool = False,
    high_risk_allowed: bool = True,
    has_debt_default: bool = False,
    emergency_reserve_months: Decimal | int | float | None = None,
) -> dict:
    constraints = apply_financial_constraints(
        risk_profile=risk_profile,
        financial_score=financial_score,
        has_debt_default=has_debt_default,
        emergency_reserve_months=emergency_reserve_months,
        emergency_reserve_priority=emergency_reserve_priority,
        high_risk_allowed=high_risk_allowed,
    )
    weights = dict(BASE_ALLOCATIONS[constraints.risk_profile])

    if financial_score < 40:
        moved = weights["cripto"]
        weights["cripto"] = Decimal("0")
        weights["renda_fixa"] += moved + Decimal("10")
        weights["acoes"] = max(Decimal("0"), weights["acoes"] - Decimal("10"))

    if constraints.emergency_reserve_priority:
        reduction = weights["acoes"] * Decimal("0.35") + weights["cripto"] * Decimal("0.70") + weights["etf"] * Decimal("0.15")
        weights["renda_fixa"] += reduction
        weights["acoes"] *= Decimal("0.65")
        weights["cripto"] *= Decimal("0.30")
        weights["etf"] *= Decimal("0.85")

    if not constraints.crypto_allowed:
        weights["renda_fixa"] += weights["cripto"]
        weights["cripto"] = Decimal("0")

    if constraints.actions_reduced:
        cut = weights["acoes"] * Decimal("0.40")
        weights["acoes"] -= cut
        weights["renda_fixa"] += cut

    percentages = _normalize_to_100(weights)
    amount = max(Decimal("0"), Decimal(str(investment_capacity or 0))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    allocation = [
        {
            "asset_class": key,
            "percentage": percentages[key],
            "amount": (amount * percentages[key] / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        }
        for key in ORDER
    ]
    amount_diff = amount - sum(item["amount"] for item in allocation)
    allocation[0]["amount"] += amount_diff
    return {"adjusted_risk_profile": constraints.risk_profile, "allocation": allocation, "warnings": constraints.warnings}
