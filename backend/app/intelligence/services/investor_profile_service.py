from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

from backend.app.intelligence.services.recommendation_guardrail_service import APPROVED, WARNING

CONSERVATIVE = "CONSERVATIVE"
MODERATE = "MODERATE"
AGGRESSIVE = "AGGRESSIVE"

VALID_PROFILES = {CONSERVATIVE, MODERATE, AGGRESSIVE}

PROFILE_DIVERSIFIED_ALLOCATIONS: dict[str, dict[str, Decimal]] = {
    CONSERVATIVE: {
        "ETF": Decimal("0.50"),
        "FII": Decimal("0.30"),
        "ACOES": Decimal("0.20"),
        "BDR": Decimal("0.00"),
    },
    MODERATE: {
        "FII": Decimal("0.40"),
        "ACOES": Decimal("0.30"),
        "ETF": Decimal("0.20"),
        "BDR": Decimal("0.10"),
    },
    AGGRESSIVE: {
        "ACOES": Decimal("0.30"),
        "FII": Decimal("0.25"),
        "ETF": Decimal("0.25"),
        "BDR": Decimal("0.20"),
    },
}


def normalize_profile(profile: str | None) -> str:
    if profile is None or str(profile).strip() == "":
        return MODERATE
    normalized = str(profile).strip().upper()
    if normalized not in VALID_PROFILES:
        raise ValueError("profile inválido. Use CONSERVATIVE, MODERATE ou AGGRESSIVE")
    return normalized


def _decimal_attr(item: Any, name: str, default: str = "0") -> Decimal:
    value = getattr(item, name, None)
    if value is None:
        return Decimal(default)
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def calculate_profile_score(item: Any, profile: str) -> Decimal:
    profile = normalize_profile(profile)
    score_total = _decimal_attr(item, "score_total")
    score_value = _decimal_attr(item, "score_value")
    score_quality = _decimal_attr(item, "score_quality")
    score_dividend = _decimal_attr(item, "score_dividend")
    score_liquidity = _decimal_attr(item, "score_liquidity")
    score_risk = _decimal_attr(item, "score_risk")

    if profile == CONSERVATIVE:
        return (
            score_quality * Decimal("0.35")
            + score_liquidity * Decimal("0.30")
            + score_risk * Decimal("0.25")
            + score_total * Decimal("0.10")
        ).quantize(Decimal("0.01"))
    if profile == AGGRESSIVE:
        return (
            score_total * Decimal("0.55")
            + score_value * Decimal("0.25")
            + score_dividend * Decimal("0.20")
        ).quantize(Decimal("0.01"))
    return score_total.quantize(Decimal("0.01"))


def apply_profile_filters(items: Iterable[Any], profile: str | None, include_warnings: bool = False) -> list[Any]:
    normalized_profile = normalize_profile(profile)
    filtered: list[Any] = []

    for item in items:
        status = str(getattr(item, "status", APPROVED) or APPROVED).upper()
        risk_level = str(getattr(item, "risk_level", "LOW") or "LOW").upper()
        score_risk = _decimal_attr(item, "score_risk", "100")

        if status == "BLOCKED":
            continue

        if normalized_profile == CONSERVATIVE:
            if status != APPROVED:
                continue
            if risk_level != "LOW":
                continue
            if score_risk < Decimal("50"):
                continue
        elif normalized_profile == MODERATE:
            if status == WARNING and not include_warnings:
                continue
            if status not in {APPROVED, WARNING}:
                continue
            if risk_level not in {"LOW", "MEDIUM"}:
                continue
        elif normalized_profile == AGGRESSIVE:
            if status == WARNING and not include_warnings:
                continue
            if status not in {APPROVED, WARNING}:
                continue

        try:
            setattr(item, "profile", normalized_profile)
            setattr(item, "profile_score", calculate_profile_score(item, normalized_profile))
        except Exception:
            pass
        filtered.append(item)

    filtered.sort(key=lambda item: (-calculate_profile_score(item, normalized_profile), str(getattr(item, "ticker", ""))))
    return filtered


def get_diversified_allocation(profile: str | None) -> dict[str, Decimal]:
    normalized_profile = normalize_profile(profile)
    return PROFILE_DIVERSIFIED_ALLOCATIONS[normalized_profile]
