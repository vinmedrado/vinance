from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from backend.app.intelligence.services.investor_profile_service import AGGRESSIVE, CONSERVATIVE, MODERATE, normalize_profile

UNKNOWN = "UNKNOWN"
CONFIDENCE_LOW = "LOW"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_VERY_LOW = "VERY_LOW"


def _to_decimal(value: Decimal | int | float | str | None, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return Decimal(default)


def _normalize_text(value: str | None, default: str = UNKNOWN) -> str:
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().upper()


def _clamp(value: Decimal) -> Decimal:
    if value < 0:
        value = Decimal("0")
    if value > 100:
        value = Decimal("100")
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_safety_score(status: str | None, risk_level: str | None) -> Decimal:
    status = _normalize_text(status, "APPROVED")
    risk_level = _normalize_text(risk_level, "LOW")

    if status == "BLOCKED":
        return Decimal("0")
    if status == "APPROVED" and risk_level == "LOW":
        return Decimal("100")
    if status == "APPROVED" and risk_level == "MEDIUM":
        return Decimal("85")
    if status == "WARNING" and risk_level == "MEDIUM":
        return Decimal("65")
    if status == "WARNING" and risk_level == "HIGH":
        return Decimal("45")
    if status == "WARNING":
        return Decimal("70")
    if risk_level == "HIGH":
        return Decimal("55")
    if risk_level == "MEDIUM":
        return Decimal("85")
    return Decimal("100")


def _trend_adjustment(trend_label: str | None) -> Decimal:
    trend = _normalize_text(trend_label, UNKNOWN)
    if trend == "UPTREND":
        return Decimal("5")
    if trend == "DOWNTREND":
        return Decimal("-8")
    if trend == "INSUFFICIENT_HISTORY":
        return Decimal("-3")
    return Decimal("0")


def _confidence_adjustment(trend_confidence: str | None) -> Decimal:
    confidence = _normalize_text(trend_confidence, "NULL")
    if confidence == CONFIDENCE_HIGH:
        return Decimal("3")
    if confidence == CONFIDENCE_MEDIUM:
        return Decimal("1")
    if confidence == CONFIDENCE_LOW:
        return Decimal("-2")
    if confidence == CONFIDENCE_VERY_LOW:
        return Decimal("-5")
    return Decimal("-3")


def calculate_recommendation_score(
    score_total: Decimal | int | float | str | None,
    profile_score: Decimal | int | float | str | None,
    status: str | None,
    risk_level: str | None,
    trend_label: str | None = None,
    momentum_score: Decimal | int | float | str | None = None,
    trend_confidence: str | None = None,
    profile: str = MODERATE,
) -> Decimal:
    """Calcula o ranking final de recomendação em runtime.

    Não persiste dados e não altera as tabelas derivadas existentes. A nota final
    combina score base, score por perfil, momentum/tendência e uma nota de
    segurança derivada dos guardrails.
    """
    normalized_profile = normalize_profile(profile)
    total = _to_decimal(score_total)
    profile_value = _to_decimal(profile_score)
    momentum = _to_decimal(momentum_score)
    safety = calculate_safety_score(status, risk_level)

    if normalized_profile == CONSERVATIVE:
        base = (
            profile_value * Decimal("0.40")
            + total * Decimal("0.25")
            + momentum * Decimal("0.20")
            + safety * Decimal("0.15")
        )
    elif normalized_profile == AGGRESSIVE:
        base = (
            profile_value * Decimal("0.30")
            + total * Decimal("0.35")
            + momentum * Decimal("0.25")
            + safety * Decimal("0.10")
        )
    else:
        base = (
            profile_value * Decimal("0.35")
            + total * Decimal("0.30")
            + momentum * Decimal("0.25")
            + safety * Decimal("0.10")
        )

    final_score = base + _trend_adjustment(trend_label) + _confidence_adjustment(trend_confidence)
    return _clamp(final_score)


def build_recommendation_components(
    *,
    score_total: Decimal | int | float | str | None,
    profile_score: Decimal | int | float | str | None,
    status: str | None,
    risk_level: str | None,
    trend_label: str | None,
    momentum_score: Decimal | int | float | str | None,
    trend_confidence: str | None,
    profile: str,
) -> dict[str, str]:
    normalized_profile = normalize_profile(profile)
    safety = calculate_safety_score(status, risk_level)
    return {
        "profile": normalized_profile,
        "score_total": str(_to_decimal(score_total)),
        "profile_score": str(_to_decimal(profile_score)),
        "momentum_score": str(_to_decimal(momentum_score)),
        "safety_score": str(safety),
        "status": _normalize_text(status, "APPROVED"),
        "risk_level": _normalize_text(risk_level, "LOW"),
        "trend_label": _normalize_text(trend_label, UNKNOWN),
        "trend_confidence": _normalize_text(trend_confidence, "NULL"),
        "trend_adjustment": str(_trend_adjustment(trend_label)),
        "confidence_adjustment": str(_confidence_adjustment(trend_confidence)),
    }
