from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable

from backend.app.investment_performance.config import (
    NEUTRAL_RETURN_THRESHOLD_PCT,
    STRONG_RETURN_THRESHOLD_PCT,
)


SIX_DECIMALS = Decimal("0.000001")
VALID_ACTIONS = {"BUY", "WAIT", "AVOID"}


def _decimal(value: Any) -> Decimal:
    try:
        converted = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("valor financeiro inválido") from exc
    if not converted.is_finite():
        raise ValueError("valor financeiro inválido")
    return converted


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(SIX_DECIMALS, rounding=ROUND_HALF_UP)


def calculate_observed_change(
    reference_price: Decimal,
    evaluation_price: Decimal,
) -> tuple[Decimal, Decimal]:
    reference = _decimal(reference_price)
    evaluation = _decimal(evaluation_price)
    if reference <= 0 or evaluation <= 0:
        raise ValueError("preços devem ser positivos")
    absolute_change = evaluation - reference
    return_pct = (absolute_change / reference) * Decimal("100")
    return _quantize(absolute_change), _quantize(return_pct)


def classify_result(action: str, return_pct: Decimal) -> str:
    normalized_action = str(action or "").strip().upper()
    if normalized_action not in VALID_ACTIONS:
        raise ValueError("ação histórica não avaliável")
    observed_return = _decimal(return_pct)
    action_adjusted_return = (
        observed_return if normalized_action == "BUY" else -observed_return
    )
    if action_adjusted_return >= STRONG_RETURN_THRESHOLD_PCT:
        return "STRONGLY_CORRECT"
    if action_adjusted_return >= NEUTRAL_RETURN_THRESHOLD_PCT:
        return "CORRECT"
    if action_adjusted_return > -NEUTRAL_RETURN_THRESHOLD_PCT:
        return "NEUTRAL"
    if action_adjusted_return > -STRONG_RETURN_THRESHOLD_PCT:
        return "INCORRECT"
    return "STRONGLY_INCORRECT"


def build_result_context(
    action: str,
    return_pct: Decimal,
    classification: str,
) -> dict[str, Any]:
    normalized_action = str(action).strip().upper()
    observed = _decimal(return_pct)
    magnitude = abs(observed)
    direction = "POSITIVE" if observed > 0 else "NEGATIVE" if observed < 0 else "FLAT"
    magnitude_band = (
        "STRONG"
        if magnitude >= STRONG_RETURN_THRESHOLD_PCT
        else "MATERIAL"
        if magnitude >= NEUTRAL_RETURN_THRESHOLD_PCT
        else "NEUTRAL"
    )
    interpretation = {
        "BUY": "measures whether buying was followed by positive price performance",
        "WAIT": "measures avoided downside or a missed rise while waiting",
        "AVOID": "measures protection from downside or a rise after avoiding",
    }[normalized_action]
    return {
        "action": normalized_action,
        "observed_direction": direction,
        "observed_return_pct": str(_quantize(observed)),
        "magnitude": magnitude_band,
        "classification": classification,
        "interpretation": interpretation,
        "causality_note": "observed asset price movement; not an executed trade result",
    }


def calculate_excursions(
    reference_price: Decimal,
    highs: Iterable[Decimal],
    lows: Iterable[Decimal],
) -> tuple[Decimal | None, Decimal | None]:
    reference = _decimal(reference_price)
    if reference <= 0:
        raise ValueError("preço de referência deve ser positivo")
    high_values = [_decimal(value) for value in highs]
    low_values = [_decimal(value) for value in lows]
    favorable = None
    adverse = None
    if high_values:
        raw_favorable = ((max(high_values) - reference) / reference) * Decimal("100")
        favorable = _quantize(max(Decimal("0"), raw_favorable))
    if low_values:
        raw_adverse = ((min(low_values) - reference) / reference) * Decimal("100")
        adverse = _quantize(min(Decimal("0"), raw_adverse))
    return favorable, adverse
