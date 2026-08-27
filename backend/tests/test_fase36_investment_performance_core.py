from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.investment_decisions.models import InvestmentDecisionAudit
from backend.app.investment_performance import service as performance_service
from backend.app.investment_performance.config import EVALUATION_POLICY_VERSION
from backend.app.investment_performance.evaluator import (
    calculate_excursions,
    calculate_observed_change,
    classify_result,
)
from backend.app.investment_performance.metrics import build_performance_summary
from backend.app.investment_performance.models import InvestmentDecisionPerformance
from backend.app.investment_performance.schemas import PerformanceSummary
from backend.app.market.models.prices import AssetPrice


UTC = timezone.utc
T0 = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)


def _decision(index: int = 1, **overrides) -> InvestmentDecisionAudit:
    values = {
        "id": index,
        "decision_id": f"36000000-0000-4000-8000-{index:012d}",
        "correlation_id": f"36000000-0000-4000-9000-{index:012d}",
        "user_id": 36,
        "created_at": T0,
        "asset": "PETR4",
        "market": "ACOES",
        "budget": Decimal("1000"),
        "investor_profile": "MODERATE",
        "recommendation": "BUY",
        "quantity": 10,
        "price": Decimal("100"),
        "invested_amount": Decimal("1000"),
        "remaining_amount": Decimal("0"),
        "risk_level": "LOW",
        "confidence": Decimal("90"),
        "trend": "UPTREND",
        "ranking": 1,
        "recommendation_score": Decimal("85"),
        "guardrail_status": "APPROVED",
        "guardrail_reasons": {"summary": ["Aprovado"]},
        "explanation": {"summary": "snapshot"},
        "request_parameters": {"budget": "1000"},
        "input_snapshot": {"asset": "PETR4"},
        "score_snapshot": {"recommendation_score": "85"},
        "response_snapshot": {"decision_action": "BUY"},
        "snapshot_schema_version": "investment-decision-audit-v1",
        "rule_version": "investment-decision-presentation-v1",
        "recommendation_engine_version": "budget-advisor-v1",
        "score_version": "vinance_score_v1",
        "guardrail_version": "vinance_guardrail_v1",
        "trend_version": "vinance_trend_v1",
        "latency_ms": 20,
        "fallback_used": False,
        "error_code": None,
        "status": "SUCCESS",
    }
    values.update(overrides)
    return InvestmentDecisionAudit(**values)


def _price(day: date, close: str, *, source: str = "brapi", index: int = 1, **overrides) -> AssetPrice:
    values = {
        "id": index,
        "ticker": "PETR4",
        "market": "acoes",
        "date": day,
        "open": Decimal(close),
        "high": Decimal(close) + Decimal("2"),
        "low": Decimal(close) - Decimal("2"),
        "close": Decimal(close),
        "volume": Decimal("1000"),
        "source": source,
        "created_at": datetime.combine(day, time.max, tzinfo=UTC),
    }
    values.update(overrides)
    return AssetPrice(**values)


def _evaluation(decision: InvestmentDecisionAudit, horizon: str, return_pct: str, **overrides):
    reference = Decimal("100")
    observed = Decimal(return_pct)
    action = decision.recommendation
    days = {"1d": 1, "7d": 7, "30d": 30}[horizon]
    values = {
        "id": decision.id * 10 + days,
        "decision_id": decision.decision_id,
        "horizon": horizon,
        "reference_price": reference,
        "reference_price_timestamp": decision.created_at,
        "price_source": "decision_snapshot",
        "evaluation_price": reference * (Decimal("1") + observed / Decimal("100")),
        "evaluation_timestamp": performance_service.observation_timestamp(
            (decision.created_at + timedelta(days=days)).date()
        ),
        "evaluation_price_source": "brapi",
        "absolute_change": observed,
        "return_pct": observed,
        "max_favorable_excursion_pct": max(observed, Decimal("0")),
        "max_adverse_excursion_pct": min(observed, Decimal("0")),
        "result_status": "EVALUATED",
        "result_classification": classify_result(action, observed),
        "result_context": {"action": action},
        "evaluation_policy_version": EVALUATION_POLICY_VERSION,
        "evaluated_at": decision.created_at + timedelta(days=days + 1),
        "created_at": decision.created_at + timedelta(days=days + 1),
    }
    values.update(overrides)
    return InvestmentDecisionPerformance(**values)


@pytest.mark.parametrize(
    ("action", "observed_return", "expected"),
    [
        ("BUY", "6", "STRONGLY_CORRECT"),
        ("BUY", "2", "CORRECT"),
        ("BUY", "0.5", "NEUTRAL"),
        ("BUY", "-2", "INCORRECT"),
        ("BUY", "-6", "STRONGLY_INCORRECT"),
        ("WAIT", "6", "STRONGLY_INCORRECT"),
        ("WAIT", "2", "INCORRECT"),
        ("WAIT", "0", "NEUTRAL"),
        ("WAIT", "-2", "CORRECT"),
        ("WAIT", "-6", "STRONGLY_CORRECT"),
        ("AVOID", "6", "STRONGLY_INCORRECT"),
        ("AVOID", "2", "INCORRECT"),
        ("AVOID", "0", "NEUTRAL"),
        ("AVOID", "-2", "CORRECT"),
        ("AVOID", "-6", "STRONGLY_CORRECT"),
    ],
)
def test_classificacao_por_acao_preserva_retorno_observado(action, observed_return, expected):
    assert classify_result(action, Decimal(observed_return)) == expected


@pytest.mark.parametrize(
    ("action", "observed_return", "expected"),
    [
        ("BUY", "5", "STRONGLY_CORRECT"),
        ("BUY", "1", "CORRECT"),
        ("BUY", "-1", "INCORRECT"),
        ("BUY", "-5", "STRONGLY_INCORRECT"),
        ("WAIT", "-5", "STRONGLY_CORRECT"),
        ("AVOID", "5", "STRONGLY_INCORRECT"),
    ],
)
def test_thresholds_exatos_sao_deterministicos(action, observed_return, expected):
    assert classify_result(action, Decimal(observed_return)) == expected


def test_variacao_e_excursoes_sao_calculadas_sem_semantica_de_trade():
    absolute, return_pct = calculate_observed_change(Decimal("100"), Decimal("112.5"))
    favorable, adverse = calculate_excursions(
        Decimal("100"),
        [Decimal("105"), Decimal("115")],
        [Decimal("98"), Decimal("91")],
    )
    assert absolute == Decimal("12.500000")
    assert return_pct == Decimal("12.500000")
    assert favorable == Decimal("15.000000")
    assert adverse == Decimal("-9.000000")


@pytest.mark.asyncio
async def test_preco_do_snapshot_e_a_referencia_preferencial_sem_consultar_provider():
    decision = _decision(price=Decimal("87.25"))

    class NeverQuery:
        async def execute(self, _statement):
            raise AssertionError("provider não deveria ser consultado")

    resolved = await performance_service.resolve_reference_price(
        NeverQuery(), decision, as_of=T0 + timedelta(days=2)
    )
    assert resolved == (Decimal("87.25"), T0, "decision_snapshot")


@pytest.mark.asyncio
async def test_fallback_da_referencia_usa_apenas_dia_anterior_e_o_mais_proximo(monkeypatch):
    decision = _decision(price=None)
    seen = {}
    rows = [
        _price(T0.date() - timedelta(days=3), "97", index=1),
        _price(T0.date() - timedelta(days=1), "99", index=2),
        _price(T0.date(), "150", index=3),
    ]

    async def fake_list_prices(_session, **kwargs):
        seen.update(kwargs)
        return [item for item in rows if kwargs["date_from"] <= item.date <= kwargs["date_to"]]

    monkeypatch.setattr(performance_service, "list_prices", fake_list_prices)
    resolved = await performance_service.resolve_reference_price(
        object(), decision, as_of=T0 + timedelta(days=2)
    )
    assert resolved == (
        Decimal("99"),
        performance_service.observation_timestamp(T0.date() - timedelta(days=1)),
        "brapi",
    )
    assert seen["date_to"] == T0.date() - timedelta(days=1)


def _patch_incremental(monkeypatch, decisions, prices, existing=None):
    captured: list[dict] = []

    async def fake_decisions(_session, **_kwargs):
        return decisions

    async def fake_existing(_session, _ids):
        return existing or {}

    async def fake_prices(_session, **kwargs):
        return [
            item
            for item in prices
            if item.ticker == kwargs["ticker"]
            and item.market == kwargs["market"]
            and kwargs["date_from"] <= item.date <= kwargs["date_to"]
            and item.created_at <= kwargs["available_at"]
            and (kwargs.get("source") is None or item.source == kwargs["source"])
        ]

    async def fake_insert(_session, rows):
        captured.extend(rows)
        return len(rows)

    monkeypatch.setattr(performance_service, "list_valid_decisions", fake_decisions)
    monkeypatch.setattr(performance_service, "list_existing_horizons", fake_existing)
    monkeypatch.setattr(performance_service, "list_prices", fake_prices)
    monkeypatch.setattr(performance_service, "insert_performances_if_absent", fake_insert)
    return captured


@pytest.mark.asyncio
async def test_decisao_nao_recebe_avaliacao_antes_de_um_dia(monkeypatch):
    decision = _decision()
    captured = _patch_incremental(monkeypatch, [decision], [])
    result = await performance_service.process_due_evaluations(
        object(), as_of=T0 + timedelta(hours=23, minutes=59)
    )
    assert result["eligible"] == 0
    assert result["created"] == 0
    assert captured == []


@pytest.mark.asyncio
async def test_horizonte_maduro_aguarda_fechamento_diario_observavel(monkeypatch):
    decision = _decision()
    next_day = _price(T0.date() + timedelta(days=1), "105")
    captured = _patch_incremental(monkeypatch, [decision], [next_day])
    result = await performance_service.process_due_evaluations(
        object(), as_of=T0 + timedelta(days=1, minutes=1)
    )
    assert result["eligible"] == 1
    assert result["pending_prices"] == 1
    assert captured == []


@pytest.mark.asyncio
async def test_horizontes_1d_7d_30d_usam_preco_do_alvo_e_nao_o_mais_recente(monkeypatch):
    decision = _decision()
    prices = [
        _price(T0.date() + timedelta(days=1), "101", index=1),
        _price(T0.date() + timedelta(days=7), "107", index=2),
        _price(T0.date() + timedelta(days=30), "130", index=3),
        _price(T0.date() + timedelta(days=31), "999", index=4),
    ]
    captured = _patch_incremental(monkeypatch, [decision], prices)
    result = await performance_service.process_due_evaluations(
        object(), as_of=performance_service.observation_timestamp(T0.date() + timedelta(days=31))
    )
    assert result["created"] == 3
    assert {row["horizon"]: row["evaluation_price"] for row in captured} == {
        "1d": Decimal("101"),
        "7d": Decimal("107"),
        "30d": Decimal("130"),
    }
    assert all(row["evaluation_price"] != Decimal("999") for row in captured)


@pytest.mark.asyncio
async def test_gap_temporal_aceita_quatro_dias_e_rejeita_o_quinto(monkeypatch):
    decision = _decision()
    within = _price(T0.date() + timedelta(days=5), "105", index=1)
    captured = _patch_incremental(monkeypatch, [decision], [within])
    result = await performance_service.process_due_evaluations(
        object(), as_of=performance_service.observation_timestamp(within.date)
    )
    assert result["created"] == 1
    assert captured[0]["horizon"] == "1d"
    assert captured[0]["evaluation_timestamp"] == performance_service.observation_timestamp(within.date)

    beyond = _price(T0.date() + timedelta(days=6), "106", index=2)
    captured = _patch_incremental(monkeypatch, [decision], [beyond])
    result = await performance_service.process_due_evaluations(
        object(), as_of=performance_service.observation_timestamp(beyond.date)
    )
    assert result["created"] == 0
    assert result["pending_prices"] >= 1
    assert captured == []


@pytest.mark.asyncio
async def test_preco_ausente_permanece_pendente_sem_placeholder(monkeypatch):
    decision = _decision(price=None)
    captured = _patch_incremental(monkeypatch, [decision], [])
    result = await performance_service.process_due_evaluations(
        object(), as_of=T0 + timedelta(days=40)
    )
    assert result["eligible"] == 3
    assert result["pending_prices"] == 3
    assert result["created"] == 0
    assert captured == []


@pytest.mark.asyncio
async def test_reexecucao_ignora_horizontes_concluidos_e_snapshot_fica_imutavel(monkeypatch):
    decision = _decision()
    before = deepcopy(
        {
            "price": decision.price,
            "response_snapshot": decision.response_snapshot,
            "score_snapshot": decision.score_snapshot,
            "recommendation": decision.recommendation,
        }
    )
    captured = _patch_incremental(
        monkeypatch,
        [decision],
        [],
        existing={decision.decision_id: {"1d", "7d", "30d"}},
    )
    result = await performance_service.process_due_evaluations(
        object(), as_of=T0 + timedelta(days=40)
    )
    assert result["already_evaluated"] == 3
    assert result["created"] == 0
    assert captured == []
    assert before == {
        "price": decision.price,
        "response_snapshot": decision.response_snapshot,
        "score_snapshot": decision.score_snapshot,
        "recommendation": decision.recommendation,
    }


def test_analytics_deterministico_cobre_dimensoes_versoes_timeline_e_calibracao():
    buy = _decision(1, recommendation="BUY", confidence=90, recommendation_score=85)
    wait = _decision(
        2,
        asset="VALE3",
        recommendation="WAIT",
        risk_level="MEDIUM",
        investor_profile="CONSERVATIVE",
        confidence=70,
        recommendation_score=65,
    )
    avoid = _decision(
        3,
        asset="MGLU3",
        recommendation="AVOID",
        risk_level="HIGH",
        investor_profile="AGGRESSIVE",
        confidence=50,
        recommendation_score=50,
        rule_version="investment-decision-presentation-v2",
        recommendation_engine_version="budget-advisor-v2",
        score_version="vinance_score_v2",
        guardrail_version="vinance_guardrail_v2",
    )
    evaluations = [
        _evaluation(buy, "1d", "10"),
        _evaluation(wait, "1d", "-2"),
        _evaluation(avoid, "1d", "2"),
    ]
    result = build_performance_summary(
        [buy, wait, avoid], evaluations, as_of=T0 + timedelta(days=40)
    )
    validated = PerformanceSummary.model_validate(result)
    assert validated.total_decisions == 3
    assert validated.eligible_decisions == 9
    assert validated.evaluated == 3
    assert validated.pending == 6
    assert validated.average_return_pct == pytest.approx(10 / 3)
    assert validated.median_return_pct == 2
    assert validated.directional_accuracy_pct == pytest.approx(200 / 3)
    assert {row.key for row in validated.by_action} == {"BUY", "WAIT", "AVOID"}
    assert {row.key for row in validated.by_asset} == {"PETR4", "VALE3", "MGLU3"}
    assert {row.key for row in validated.by_risk} == {"LOW", "MEDIUM", "HIGH"}
    assert {row.key for row in validated.by_trend} == {"UPTREND"}
    assert {row.key for row in validated.by_confidence} == {"LOW", "MEDIUM", "HIGH"}
    assert {row.key for row in validated.by_score_band} == {"LOW", "MEDIUM", "HIGH"}
    assert {row.key for row in validated.by_profile} == {
        "CONSERVATIVE",
        "MODERATE",
        "AGGRESSIVE",
    }
    assert len(validated.by_rule_version) == 2
    assert len(validated.by_recommendation_engine_version) == 2
    assert len(validated.by_score_version) == 2
    assert len(validated.by_guardrail_version) == 2
    assert validated.mixed_versions is True
    assert len(validated.by_version_cohort) == 2
    assert validated.by_version_cohort[0].model_extra["rule_version"]
    assert validated.timeline
    assert validated.calibration_summary["interpretation"] == "INSUFFICIENT_SAMPLE"
    assert all(row.model_extra["diagnostic"] == "INSUFFICIENT_SAMPLE" for row in validated.calibration)


def test_analytics_sem_historico_e_apenas_imatura_nao_fabrica_resultados():
    empty = PerformanceSummary.model_validate(
        build_performance_summary([], [], as_of=T0)
    )
    immature = PerformanceSummary.model_validate(
        build_performance_summary([_decision()], [], as_of=T0 + timedelta(hours=1))
    )
    assert empty.total_decisions == empty.evaluated == empty.pending == 0
    assert empty.average_return_pct is None
    assert immature.total_decisions == 1
    assert immature.eligible_decisions == immature.evaluated == immature.pending == 0
    assert all(row.evaluated == 0 for row in immature.by_horizon)
