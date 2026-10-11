from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.app.investment_orchestrator import context
from backend.app.market.models import RendaFixaProduto


NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)


class _Result:
    def __init__(self, items=None, one=None):
        self.items = items or []
        self.one = one

    def scalars(self):
        return self

    def all(self):
        return self.items

    def scalar_one_or_none(self):
        return self.one


class _Session:
    def __init__(self, results):
        self.results = list(results)

    async def execute(self, _query):
        value = self.results.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def _inputs(member_ids=(1,)):
    return {
        "members": [
            {"user_id": user_id, "full_name": f"Member {user_id}", "status": "ACTIVE"}
            for user_id in member_ids
        ],
        "assets": [],
    }


@pytest.mark.asyncio
async def test_profile_absence_is_missing_and_never_defaults_to_moderate() -> None:
    result = await context.load_profile_context(
        _Session([_Result(items=[])]), normalized_inputs=_inputs()
    )
    assert result["status"] == "MISSING"
    assert result["effective_profile"] is None
    assert result["missing_member_user_ids"] == [1]


@pytest.mark.asyncio
async def test_legacy_pre_privacy_profiles_keep_replay_behavior() -> None:
    profiles = [
        SimpleNamespace(user_id=1, risk_profile="AGGRESSIVE", updated_at=NOW),
        SimpleNamespace(user_id=2, risk_profile="CONSERVATIVE", updated_at=NOW),
    ]
    result = await context.load_profile_context(
        _Session([_Result(items=profiles)]), normalized_inputs=_inputs((1, 2))
    )
    assert result["status"] == "MIXED"
    assert result["effective_profile"] == "CONSERVATIVE"


@pytest.mark.asyncio
async def test_personal_privacy_contract_uses_frozen_profile_without_database_read() -> None:
    inputs = _inputs()
    inputs.update(
        {
            "privacy_contract_version": "household-privacy-v1",
            "decision_scope": "PERSONAL",
            "household": {"household_type": "PERSONAL"},
            "financial_profiles": [
                {
                    "user_id": 1,
                    "risk_profile": "CONSERVATIVE",
                    "updated_at": NOW,
                }
            ],
        }
    )

    result = await context.load_profile_context(_Session([]), normalized_inputs=inputs)

    assert result["status"] == "COMPLETE"
    assert result["effective_profile"] == "CONSERVATIVE"
    assert result["members"][0]["user_id"] == 1


@pytest.mark.asyncio
async def test_shared_privacy_contract_never_reads_or_identifies_personal_profiles() -> None:
    inputs = _inputs((1, 2))
    inputs.update(
        {
            "privacy_contract_version": "household-privacy-v1",
            "decision_scope": "HOUSEHOLD_SHARED",
            "household": {"household_type": "SHARED"},
            "financial_profiles": [
                {
                    "user_id": 1,
                    "risk_profile": "AGGRESSIVE",
                    "investment_horizon_months": 240,
                    "updated_at": NOW,
                },
                {
                    "user_id": 2,
                    "risk_profile": "CONSERVATIVE",
                    "investment_horizon_months": 12,
                    "updated_at": NOW,
                },
            ],
        }
    )

    result = await context.load_profile_context(_Session([]), normalized_inputs=inputs)

    assert result["status"] == "MISSING"
    assert result["effective_profile"] is None
    assert result["investment_horizon_months"] is None
    assert result["members"] == []
    assert result["missing_member_user_ids"] == []
    assert result["source"] == "household_profile.unavailable"


@pytest.mark.asyncio
async def test_absent_owned_investments_remain_unknown_not_zero() -> None:
    result = await context.load_portfolio_context(
        _Session([]), normalized_inputs=_inputs()
    )
    assert result["status"] == "UNKNOWN"
    assert result["total_known_value"] is None
    assert result["positions"] == []


@pytest.mark.asyncio
async def test_foreign_portfolio_without_fx_is_partial_and_not_zero() -> None:
    inputs = _inputs()
    inputs["assets"] = [
        {
            "id": 7,
            "status": "ACTIVE",
            "asset_class": "INVESTMENTS",
            "name": "Foreign position",
            "current_value": Decimal("125.00"),
            "currency": "USD",
            "asset_catalog_id": None,
            "ownership_scope": "PERSONAL",
            "user_id": 1,
            "value_as_of": NOW,
        }
    ]

    result = await context.load_portfolio_context(
        _Session([]), normalized_inputs=inputs
    )

    assert result["status"] == "PARTIAL"
    assert result["total_known_value"] is None
    assert "owned_assets.7.currency_conversion_missing" in result["missing_information"]


@pytest.mark.asyncio
async def test_real_zero_brl_portfolio_remains_explicit_zero() -> None:
    inputs = _inputs()
    inputs["assets"] = [
        {
            "id": 8,
            "status": "ACTIVE",
            "asset_class": "INVESTMENTS",
            "name": "Zero position",
            "current_value": Decimal("0.00"),
            "currency": "BRL",
            "asset_catalog_id": None,
            "ownership_scope": "PERSONAL",
            "user_id": 1,
            "value_as_of": NOW,
        }
    ]

    result = await context.load_portfolio_context(
        _Session([]), normalized_inputs=inputs
    )

    assert result["status"] == "PARTIAL"
    assert result["total_known_value"] == Decimal("0.00")


def _score():
    return SimpleNamespace(
        id=10,
        ticker="TEST3",
        market="ACOES",
        date=date(2026, 9, 18),
        score_total=Decimal("80"),
        score_value=Decimal("70"),
        score_quality=Decimal("75"),
        score_dividend=Decimal("60"),
        score_liquidity=Decimal("90"),
        score_risk=Decimal("80"),
        price=Decimal("100"),
        metadata_json={"source_snapshot": "score-10"},
        calculated_at=NOW,
        source="vinance_score_v1",
    )


def _guardrail(status="APPROVED"):
    return SimpleNamespace(
        id=20,
        ticker="TEST3",
        market="ACOES",
        date=date(2026, 9, 18),
        status=status,
        risk_level="LOW",
        reasons_json={"blocked": [], "warnings": [], "summary": []},
        calculated_at=NOW,
        source="vinance_guardrail_v1",
    )


@pytest.mark.asyncio
async def test_score_without_exact_guardrail_is_never_promoted(monkeypatch) -> None:
    monkeypatch.setattr(context, "SUPPORTED_MARKETS", ("ACOES",))

    async def common(*_args, **_kwargs):
        return date(2026, 9, 18)

    monkeypatch.setattr(context, "_latest_common_market_date", common)
    session = _Session(
        [
            _Result(items=[_score()]),
            _Result(items=[]),
            _Result(items=[]),
            _Result(items=[]),
        ]
    )
    result = await context.load_market_context(
        session,
        investment_budget=Decimal("1000"),
        profile="MODERATE",
        captured_at=NOW,
    )
    assert result["candidates"] == []
    assert result["markets"][0]["missing_guardrail_count"] == 1


@pytest.mark.asyncio
async def test_strict_candidate_freezes_score_guardrail_catalog_and_sources(monkeypatch) -> None:
    monkeypatch.setattr(context, "SUPPORTED_MARKETS", ("ACOES",))

    async def common(*_args, **_kwargs):
        return date(2026, 9, 18)

    monkeypatch.setattr(context, "_latest_common_market_date", common)
    catalog = SimpleNamespace(id=30, ticker="TEST3", market="ACOES", name="Test SA")
    session = _Session(
        [
            _Result(items=[_score()]),
            _Result(items=[_guardrail()]),
            _Result(items=[catalog]),
            _Result(items=[]),
        ]
    )
    result = await context.load_market_context(
        session,
        investment_budget=Decimal("1000"),
        profile="MODERATE",
        captured_at=NOW,
    )
    candidate = result["candidates"][0]
    assert candidate["asset_id"] == 30
    assert candidate["score_id"] == 10
    assert candidate["guardrail_id"] == 20
    assert candidate["guardrail_status"] == "APPROVED"
    assert candidate["score_source"] == "vinance_score_v1"
    assert candidate["liquidity_score"] == Decimal("90")


@pytest.mark.asyncio
async def test_provider_failure_isolated_per_market(monkeypatch) -> None:
    monkeypatch.setattr(context, "SUPPORTED_MARKETS", ("ACOES", "ETF"))
    session = _Session([RuntimeError("provider down"), RuntimeError("provider down")])
    result = await context.load_market_context(
        session,
        investment_budget=Decimal("1000"),
        profile="MODERATE",
        captured_at=NOW,
    )
    assert result["status"] == "UNAVAILABLE"
    assert {item["market"] for item in result["partial_failures"]} == {"ACOES", "ETF"}


@pytest.mark.asyncio
async def test_fixed_income_failure_does_not_hide_available_equity_market(monkeypatch) -> None:
    monkeypatch.setattr(context, "SUPPORTED_MARKETS", ("ACOES", "FIXED_INCOME"))

    async def common(*_args, **_kwargs):
        return date(2026, 9, 18)

    monkeypatch.setattr(context, "_latest_common_market_date", common)
    catalog = SimpleNamespace(id=30, ticker="TEST3", market="ACOES", name="Test SA")
    session = _Session(
        [
            _Result(items=[_score()]),
            _Result(items=[_guardrail()]),
            _Result(items=[catalog]),
            _Result(items=[]),
            RuntimeError("treasury provider unavailable"),
        ]
    )

    result = await context.load_market_context(
        session,
        investment_budget=Decimal("1000"),
        profile="MODERATE",
        captured_at=NOW,
    )

    assert result["status"] == "AVAILABLE"
    assert any(item["market"] == "ACOES" for item in result["markets"])
    assert {item["market"] for item in result["partial_failures"]} == {
        "FIXED_INCOME"
    }
    assert all(item["market"] != "FIXED_INCOME" for item in result["candidates"])


@pytest.mark.asyncio
async def test_fixed_income_context_uses_canonical_product_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(context, "SUPPORTED_MARKETS", ("FIXED_INCOME",))
    product = RendaFixaProduto(
        id=41,
        source_product_id="tesouro-selic:2031-03-01",
        asset_catalog_id=31,
        nome="Tesouro Selic 2031",
        emissor="Tesouro Nacional",
        tipo="TREASURY_SELIC",
        indexador="SELIC",
        purchase_rate=Decimal("0.05"),
        redemption_rate=Decimal("0.06"),
        unit_price=Decimal("15000.00"),
        redemption_unit_price=Decimal("14990.00"),
        base_unit_price=Decimal("14995.00"),
        vencimento=date(2031, 3, 1),
        liquidity_type="DAILY_REPURCHASE",
        investimento_minimo=Decimal("150.00"),
        garantia_fgc=False,
        guarantee_type="SOVEREIGN_ISSUER",
        currency="BRL",
        market_date=date(2026, 9, 18),
        source="tesouro_transparente",
        coletado_em=NOW,
        is_active=True,
    )
    catalog = SimpleNamespace(
        id=31,
        ticker="TD-TEST",
        market="renda_fixa",
        name="Tesouro Selic 2031",
    )
    session = _Session([_Result(items=[product]), _Result(items=[catalog])])

    result = await context.load_market_context(
        session,
        investment_budget=Decimal("1000"),
        profile="CONSERVATIVE",
        captured_at=NOW,
    )

    assert result["status"] == "AVAILABLE"
    assert result["markets"][0]["market"] == "FIXED_INCOME"
    candidate = result["candidates"][0]
    assert candidate["action"] == "BUY"
    assert candidate["purchase_mode"] == "AMOUNT"
    assert candidate["minimum_investment"] == Decimal("150.00")
    assert candidate["asset_id"] == 31
