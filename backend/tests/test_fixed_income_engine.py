from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from backend.app.fixed_income.engine import evaluate_fixed_income_product


AS_OF = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


def _product(**overrides):
    value = {
        "id": 10,
        "source_product_id": "tesouro-selic:2029-03-01",
        "asset_catalog_id": 20,
        "catalog_ticker": "TD-ABC",
        "nome": "Tesouro Selic 2029",
        "tipo": "TREASURY_SELIC",
        "indexador": "SELIC",
        "purchase_rate": Decimal("0.05"),
        "redemption_rate": Decimal("0.06"),
        "unit_price": Decimal("20046.46"),
        "investimento_minimo": Decimal("200.47"),
        "vencimento": date(2029, 3, 1),
        "liquidity_type": "DAILY_REPURCHASE",
        "liquidez_dias": None,
        "guarantee_type": "SOVEREIGN_ISSUER",
        "tax_treatment": None,
        "currency": "BRL",
        "market_date": date(2026, 10, 9),
        "source": "tesouro_transparente",
        "is_active": True,
    }
    value.update(overrides)
    return value


def _evaluate(product=None, **overrides):
    parameters = {
        "investment_budget": Decimal("1000.00"),
        "profile": "CONSERVATIVE",
        "investment_horizon_months": None,
        "as_of": AS_OF,
    }
    parameters.update(overrides)
    return evaluate_fixed_income_product(product or _product(), **parameters)


def test_liquid_treasury_selic_with_unknown_horizon_can_be_evaluated() -> None:
    result = _evaluate()

    assert result["eligibility"] == "ELIGIBLE"
    assert result["action"] == "BUY"
    assert result["guardrail_status"] == "APPROVED"
    assert result["candidate_amount"] == Decimal("1000.00")
    assert result["purchase_mode"] == "AMOUNT"


def test_duration_sensitive_product_waits_when_horizon_is_unknown() -> None:
    result = _evaluate(
        _product(
            tipo="TREASURY_IPCA",
            indexador="IPCA",
            source_product_id="tesouro-ipca:2045-05-15",
            nome="Tesouro IPCA+ 2045",
            vencimento=date(2045, 5, 15),
        ),
        profile="MODERATE",
    )

    assert result["eligibility"] == "LIMITED"
    assert result["action"] == "WAIT"
    assert "INVESTMENT_HORIZON_UNKNOWN" in {
        item["code"] for item in result["warnings"]
    }


def test_known_horizon_must_fit_duration_sensitive_maturity() -> None:
    product = _product(
        tipo="TREASURY_PREFIXED",
        indexador="PREFIXED",
        source_product_id="tesouro-prefixado:2035-01-01",
        nome="Tesouro Prefixado 2035",
        vencimento=date(2035, 1, 1),
    )

    limited = _evaluate(product, profile="MODERATE", investment_horizon_months=24)
    eligible = _evaluate(product, profile="MODERATE", investment_horizon_months=240)

    assert limited["action"] == "WAIT"
    assert limited["maturity_fit"] == "INCOMPATIBLE"
    assert eligible["action"] == "BUY"
    assert eligible["maturity_fit"] == "COMPATIBLE"


def test_stale_inactive_expired_and_wrong_currency_never_buy() -> None:
    stale = _evaluate(_product(market_date=date(2026, 9, 1)))
    inactive = _evaluate(_product(is_active=False))
    expired = _evaluate(_product(vencimento=date(2026, 10, 10)))
    currency = _evaluate(_product(currency="USD"))

    assert stale["action"] == "WAIT"
    assert inactive["action"] == "AVOID"
    assert expired["action"] == "AVOID"
    assert currency["action"] == "AVOID"


def test_freshness_boundary_is_five_calendar_days() -> None:
    fifth_day = _evaluate(_product(market_date=date(2026, 10, 6)))
    sixth_day = _evaluate(_product(market_date=date(2026, 10, 5)))

    assert fifth_day["freshness_status"] == "FRESH"
    assert fifth_day["action"] == "BUY"
    assert sixth_day["freshness_status"] == "STALE"
    assert sixth_day["action"] == "WAIT"


def test_missing_currency_is_not_reinterpreted_as_brl() -> None:
    result = _evaluate(_product(currency=None))

    assert result["action"] == "AVOID"
    assert result["currency"] is None
    assert "currency" in {
        field
        for blocker in result["blockers"]
        for field in blocker["fields"]
    }


def test_minimum_investment_respects_zero_equal_and_insufficient_budget() -> None:
    equal = _evaluate(investment_budget=Decimal("200.47"))
    below = _evaluate(investment_budget=Decimal("200.46"))
    zero = _evaluate(investment_budget=Decimal("0.00"))

    assert equal["action"] == "BUY"
    assert equal["candidate_amount"] == Decimal("200.47")
    assert below["action"] == "WAIT"
    assert zero["action"] == "AVOID"
    assert zero["candidate_amount"] == Decimal("0.00")
    assert "NO_AUTHORIZED_INVESTMENT_BUDGET" in {
        item["code"] for item in zero["blockers"]
    }


def test_missing_value_is_not_reinterpreted_as_zero() -> None:
    result = _evaluate(_product(unit_price=None))

    assert result["action"] == "AVOID"
    assert "unit_price" in result["blockers"][0]["fields"]
    assert result["price_reference"] is None


def test_real_zero_rate_is_not_reinterpreted_as_missing() -> None:
    result = _evaluate(_product(purchase_rate=Decimal("0"), taxa_juros=None))

    assert result["reference_rate"] == Decimal("0")
    assert not any(
        "purchase_rate" in item["fields"] for item in result["blockers"]
    )


def test_nominal_rate_does_not_drive_suitability_score() -> None:
    low_rate = _evaluate(_product(purchase_rate=Decimal("0.01")))
    high_rate = _evaluate(_product(purchase_rate=Decimal("99.99")))

    assert low_rate["recommendation_score"] == high_rate["recommendation_score"]


def test_same_frozen_inputs_are_deterministic() -> None:
    first = _evaluate()
    second = _evaluate()

    assert first == second
