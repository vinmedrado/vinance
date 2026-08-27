from __future__ import annotations

import importlib.util
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import UniqueConstraint

from backend.app.investment_alerts.evaluator import (
    Observation,
    action_change_severity,
    build_evaluation_key,
    build_occurrence_key,
    cooldown_allows,
    detect_relevant_events,
    risk_change_severity,
)
from backend.app.investment_alerts.models import (
    InvestmentAlert,
    InvestmentAlertState,
    InvestmentAlertSubscription,
)
from backend.app.investment_alerts.rules import (
    ALERT_RULE_VERSION,
    ALERT_TYPE_ACTION_CHANGE,
    ALERT_TYPE_CONFIDENCE_CHANGE,
    ALERT_TYPE_NEW_OPPORTUNITY,
    ALERT_TYPE_RISK_CHANGE,
    ALERT_TYPE_SCORE_CHANGE,
    ALERT_TYPES,
    DEFAULT_COOLDOWN_MINUTES,
    DEFAULT_MINIMUM_CONFIDENCE_DELTA,
    DEFAULT_MINIMUM_SCORE_DELTA,
    DELIVERY_CHANNEL_IN_APP,
    EVENT_PRIORITY,
    MAXIMUM_COOLDOWN_MINUTES,
    MAX_ACTIVE_SUBSCRIPTIONS_PER_USER,
    MAX_ALERTS_PER_CYCLE,
    MAX_ALERTS_PER_SUBSCRIPTION_EVALUATION,
    MAX_SUBSCRIPTIONS_PER_CYCLE,
    MINIMUM_ALLOWED_CONFIDENCE_DELTA,
    MINIMUM_ALLOWED_SCORE_DELTA,
    MINIMUM_COOLDOWN_MINUTES,
    SEVERITIES,
    SEVERITY_HIGH,
    SEVERITY_INFO,
    SEVERITY_MEDIUM,
    SEVERITY_ORDER,
    VALID_ACTIONS,
    VALID_RISK_LEVELS,
)
from backend.app.investment_alerts.schemas import (
    AlertDetail,
    SubscriptionCreate,
    SubscriptionPreferences,
    SubscriptionUpdate,
)


UTC = timezone.utc
NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
DECISION_ID = "37000000-0000-4000-8000-000000000001"
ALERT_ID = "37000000-0000-4000-8000-000000000002"


def _observation(**overrides) -> Observation:
    values = {
        "decision_id": DECISION_ID,
        "action": "WAIT",
        "score": Decimal("70"),
        "confidence": Decimal("75"),
        "risk_level": "LOW",
        "trend": "SIDEWAYS",
        "observed_at": NOW,
    }
    values.update(overrides)
    return Observation.from_values(**values)


def _events(previous: Observation, current: Observation, **overrides):
    values = {
        "subscription_id": 37,
        "asset": "PETR4",
        "previous": previous,
        "current": current,
        "alert_on_action_change": True,
        "alert_on_score_change": True,
        "alert_on_confidence_change": True,
        "alert_on_risk_change": True,
        "alert_on_new_opportunity": True,
        "minimum_score_delta": Decimal("5"),
        "minimum_confidence_delta": Decimal("10"),
    }
    values.update(overrides)
    return detect_relevant_events(**values)


def _unique_column_sets(model) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in model.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _foreign_key_targets(model) -> set[str]:
    return {
        foreign_key.target_fullname
        for column in model.__table__.columns
        for foreign_key in column.foreign_keys
    }


def test_regras_centrais_definem_vocabulario_e_prioridade_sem_numeros_magicos():
    assert ALERT_RULE_VERSION
    assert DELIVERY_CHANNEL_IN_APP == "IN_APP"
    assert set(ALERT_TYPES) == {
        ALERT_TYPE_NEW_OPPORTUNITY,
        ALERT_TYPE_ACTION_CHANGE,
        ALERT_TYPE_SCORE_CHANGE,
        ALERT_TYPE_CONFIDENCE_CHANGE,
        ALERT_TYPE_RISK_CHANGE,
    }
    assert set(SEVERITIES) == {SEVERITY_INFO, SEVERITY_MEDIUM, SEVERITY_HIGH}
    assert set(VALID_ACTIONS) == {"BUY", "WAIT", "AVOID"}
    assert set(VALID_RISK_LEVELS) == {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}
    assert EVENT_PRIORITY[ALERT_TYPE_NEW_OPPORTUNITY] > EVENT_PRIORITY[ALERT_TYPE_ACTION_CHANGE]
    assert SEVERITY_ORDER[SEVERITY_HIGH] > SEVERITY_ORDER[SEVERITY_MEDIUM] > SEVERITY_ORDER[SEVERITY_INFO]


def test_defaults_e_limites_operacionais_sao_coerentes_e_centrais():
    assert DEFAULT_MINIMUM_SCORE_DELTA >= MINIMUM_ALLOWED_SCORE_DELTA > 0
    assert DEFAULT_MINIMUM_CONFIDENCE_DELTA >= MINIMUM_ALLOWED_CONFIDENCE_DELTA > 0
    assert MINIMUM_COOLDOWN_MINUTES <= DEFAULT_COOLDOWN_MINUTES <= MAXIMUM_COOLDOWN_MINUTES
    assert 0 < MAX_ACTIVE_SUBSCRIPTIONS_PER_USER <= MAX_SUBSCRIPTIONS_PER_CYCLE
    assert 0 < MAX_ALERTS_PER_SUBSCRIPTION_EVALUATION <= MAX_ALERTS_PER_CYCLE


def test_subscription_preferences_usam_defaults_centrais():
    preferences = SubscriptionPreferences()
    assert preferences.alert_on_action_change is True
    assert preferences.alert_on_score_change is True
    assert preferences.alert_on_confidence_change is True
    assert preferences.alert_on_risk_change is True
    assert preferences.alert_on_new_opportunity is True
    assert preferences.minimum_score_delta == DEFAULT_MINIMUM_SCORE_DELTA
    assert preferences.minimum_confidence_delta == DEFAULT_MINIMUM_CONFIDENCE_DELTA
    assert preferences.cooldown_minutes == DEFAULT_COOLDOWN_MINUTES


@pytest.mark.parametrize("asset", ["PETR4", "CPTS11", "BTC-BRL", "BRK.B"])
def test_subscription_create_aceita_apenas_identificador_de_ativo_seguro(asset):
    payload = SubscriptionCreate(asset=asset, source_decision_id=DECISION_ID)
    assert payload.asset == asset


@pytest.mark.parametrize(
    "asset",
    ["", "PETR4' OR 1=1 --", "../../segredo", "PETR4;DROP TABLE users", "ação com espaço"],
)
def test_subscription_create_rejeita_ativo_vazio_ou_injection(asset):
    with pytest.raises(ValidationError):
        SubscriptionCreate(asset=asset)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("minimum_score_delta", MINIMUM_ALLOWED_SCORE_DELTA - Decimal("0.0001")),
        ("minimum_confidence_delta", MINIMUM_ALLOWED_CONFIDENCE_DELTA - Decimal("0.0001")),
        ("cooldown_minutes", MINIMUM_COOLDOWN_MINUTES - 1),
        ("cooldown_minutes", MAXIMUM_COOLDOWN_MINUTES + 1),
    ],
)
def test_subscription_update_rejeita_thresholds_e_cooldown_fora_da_politica(field, value):
    with pytest.raises(ValidationError):
        SubscriptionUpdate(**{field: value})


def test_models_expoem_tabelas_aditivas_e_constraints_de_idempotencia():
    assert InvestmentAlertSubscription.__tablename__ == "investment_alert_subscriptions"
    assert InvestmentAlertState.__tablename__ == "investment_alert_states"
    assert InvestmentAlert.__tablename__ == "investment_alerts"

    assert ("user_id", "asset") in _unique_column_sets(InvestmentAlertSubscription)
    assert ("subscription_id",) in _unique_column_sets(InvestmentAlertState)
    assert ("user_id", "asset") in _unique_column_sets(InvestmentAlertState)
    assert ("alert_id",) in _unique_column_sets(InvestmentAlert)
    assert ("deduplication_key",) in _unique_column_sets(InvestmentAlert)


def test_models_preservam_ownership_e_referencias_a_fase35():
    subscription_targets = _foreign_key_targets(InvestmentAlertSubscription)
    state_targets = _foreign_key_targets(InvestmentAlertState)
    alert_targets = _foreign_key_targets(InvestmentAlert)

    assert "users.id" in subscription_targets
    assert "investment_decision_audits.decision_id" in subscription_targets
    assert "users.id" in state_targets
    assert "investment_alert_subscriptions.id" in state_targets
    assert "investment_decision_audits.decision_id" in state_targets
    assert "users.id" in alert_targets
    assert "investment_alert_subscriptions.id" in alert_targets
    assert "investment_decision_audits.decision_id" in alert_targets


def test_alerta_armazena_snapshot_factual_e_canal_in_app_sem_provider_externo():
    alert = InvestmentAlert(
        alert_id=ALERT_ID,
        deduplication_key="a" * 64,
        user_id=37,
        subscription_id=1,
        decision_id=DECISION_ID,
        asset="PETR4",
        alert_type=ALERT_TYPE_ACTION_CHANGE,
        severity=SEVERITY_HIGH,
        delivery_channel=DELIVERY_CHANNEL_IN_APP,
        previous_state={"action": "WAIT", "score": "70"},
        current_state={"action": "BUY", "score": "82"},
        message="A recomendação mudou de Aguardar para Comprar.",
        rule_version=ALERT_RULE_VERSION,
        created_at=NOW,
    )
    detail = AlertDetail.model_validate(alert)
    assert detail.delivery_channel == "IN_APP"
    assert detail.previous_state == {"action": "WAIT", "score": "70"}
    assert detail.current_state == {"action": "BUY", "score": "82"}
    assert detail.read_at is None
    assert "garant" not in detail.message.lower()


def test_observation_normaliza_valores_sem_fabricar_confidence_ausente():
    observation = Observation.from_values(
        decision_id=DECISION_ID,
        action=" buy ",
        score="82.5000",
        confidence=None,
        risk_level=" medium ",
        trend=" uptrend ",
        observed_at=NOW,
    )
    assert observation.action == "BUY"
    assert observation.score == Decimal("82.5000")
    assert observation.confidence is None
    assert observation.risk_level == "MEDIUM"
    assert observation.trend == "UPTREND"
    assert observation.snapshot() == {
        "decision_id": DECISION_ID,
        "action": "BUY",
        "score": "82.5",
        "confidence": None,
        "risk_level": "MEDIUM",
        "trend": "UPTREND",
        "observed_at": NOW.isoformat(),
    }


@pytest.mark.parametrize(
    ("previous", "current", "expected"),
    [
        ("BUY", "WAIT", SEVERITY_MEDIUM),
        ("BUY", "AVOID", SEVERITY_HIGH),
        ("WAIT", "BUY", SEVERITY_HIGH),
        ("WAIT", "AVOID", SEVERITY_MEDIUM),
        ("AVOID", "WAIT", SEVERITY_INFO),
        ("AVOID", "BUY", SEVERITY_HIGH),
    ],
)
def test_severidade_das_seis_transicoes_de_acao(previous, current, expected):
    assert action_change_severity(previous, current) == expected


@pytest.mark.parametrize("previous_action", ["WAIT", "AVOID", None])
def test_buy_novo_e_classificado_como_new_opportunity_sem_alerta_de_acao_duplicado(previous_action):
    previous = _observation(action=previous_action)
    current = _observation(
        decision_id="37000000-0000-4000-8000-000000000003",
        action="BUY",
    )
    events = _events(previous, current)
    assert [event.alert_type for event in events] == [ALERT_TYPE_NEW_OPPORTUNITY]
    assert events[0].severity == SEVERITY_HIGH
    assert "nova oportunidade" in events[0].message.lower()
    assert "compre agora" not in events[0].message.lower()


def test_new_opportunity_desabilitada_preserva_action_change_quando_configurado():
    events = _events(
        _observation(action="WAIT"),
        _observation(action="BUY"),
        alert_on_new_opportunity=False,
    )
    assert [event.alert_type for event in events] == [ALERT_TYPE_ACTION_CHANGE]
    assert events[0].severity == SEVERITY_HIGH


def test_action_change_respeita_preferencia_e_nao_alerta_estado_identico():
    assert _events(
        _observation(action="BUY"),
        _observation(action="WAIT"),
        alert_on_action_change=False,
    ) == []
    assert _events(_observation(action="WAIT"), _observation(action="WAIT")) == []


@pytest.mark.parametrize(
    ("previous_score", "current_score", "should_alert"),
    [
        ("70", "74.9999", False),
        ("70", "75", True),
        ("70", "65", True),
        ("0", "5", True),
    ],
)
def test_score_delta_aplica_threshold_absoluto_inclusive(previous_score, current_score, should_alert):
    events = _events(
        _observation(score=previous_score),
        _observation(score=current_score),
        alert_on_action_change=False,
        alert_on_confidence_change=False,
        alert_on_risk_change=False,
        alert_on_new_opportunity=False,
    )
    assert (len(events) == 1) is should_alert
    if should_alert:
        event = events[0]
        assert event.alert_type == ALERT_TYPE_SCORE_CHANGE
        assert event.severity == SEVERITY_MEDIUM
        assert event.previous_state["score"] == format(Decimal(previous_score).normalize(), "f")
        assert event.current_state["score"] == format(Decimal(current_score).normalize(), "f")


@pytest.mark.parametrize("previous_confidence,current_confidence", [(None, "90"), ("80", None)])
def test_confidence_ausente_e_ausencia_legitima_sem_alerta(previous_confidence, current_confidence):
    events = _events(
        _observation(confidence=previous_confidence),
        _observation(confidence=current_confidence),
        alert_on_action_change=False,
        alert_on_score_change=False,
        alert_on_risk_change=False,
        alert_on_new_opportunity=False,
    )
    assert events == []


@pytest.mark.parametrize(
    ("previous_confidence", "current_confidence", "should_alert"),
    [("70", "79.9999", False), ("70", "80", True), ("80", "70", True)],
)
def test_confidence_delta_aplica_threshold_absoluto_inclusive(
    previous_confidence, current_confidence, should_alert
):
    events = _events(
        _observation(confidence=previous_confidence),
        _observation(confidence=current_confidence),
        alert_on_action_change=False,
        alert_on_score_change=False,
        alert_on_risk_change=False,
        alert_on_new_opportunity=False,
    )
    assert (len(events) == 1) is should_alert
    if should_alert:
        assert events[0].alert_type == ALERT_TYPE_CONFIDENCE_CHANGE
        assert events[0].severity == SEVERITY_MEDIUM


@pytest.mark.parametrize(
    ("previous", "current", "expected"),
    [
        ("LOW", "MEDIUM", SEVERITY_MEDIUM),
        ("LOW", "HIGH", SEVERITY_HIGH),
        ("MEDIUM", "HIGH", SEVERITY_HIGH),
        ("HIGH", "MEDIUM", SEVERITY_INFO),
        ("HIGH", "LOW", SEVERITY_INFO),
    ],
)
def test_risk_change_severity_nao_exagera_reducao_de_risco(previous, current, expected):
    assert risk_change_severity(previous, current) == expected
    events = _events(
        _observation(risk_level=previous),
        _observation(risk_level=current),
        alert_on_action_change=False,
        alert_on_score_change=False,
        alert_on_confidence_change=False,
        alert_on_new_opportunity=False,
    )
    assert len(events) == 1
    assert events[0].alert_type == ALERT_TYPE_RISK_CHANGE
    assert events[0].severity == expected
    assert "nível de risco" in events[0].message.lower()


def test_eventos_multiplos_sao_ordenados_e_limitados_deterministicamente():
    events = _events(
        _observation(action="AVOID", score="40", confidence="40", risk_level="LOW"),
        _observation(action="BUY", score="80", confidence="80", risk_level="HIGH"),
    )
    assert len(events) == MAX_ALERTS_PER_SUBSCRIPTION_EVALUATION
    assert [event.alert_type for event in events] == [
        ALERT_TYPE_NEW_OPPORTUNITY,
        ALERT_TYPE_RISK_CHANGE,
        ALERT_TYPE_SCORE_CHANGE,
        ALERT_TYPE_CONFIDENCE_CHANGE,
    ]
    assert [SEVERITY_ORDER[event.severity] for event in events] == sorted(
        (SEVERITY_ORDER[event.severity] for event in events), reverse=True
    )


def test_occurrence_key_e_estavel_para_retry_e_muda_com_ocorrencia_material():
    previous = _observation(action="WAIT", score="70")
    current = _observation(action="BUY", score="80")
    kwargs = {
        "subscription_id": 37,
        "alert_type": ALERT_TYPE_NEW_OPPORTUNITY,
        "previous": previous,
        "current": current,
        "material": {"previous": "WAIT", "current": "BUY"},
    }
    first = build_occurrence_key(**kwargs)
    assert first == build_occurrence_key(**kwargs)
    assert len(first) == 64
    assert first != build_occurrence_key(**{**kwargs, "subscription_id": 38})
    assert first != build_occurrence_key(
        **{
            **kwargs,
            "material": {"previous": "WAIT", "current": "AVOID"},
        }
    )


def test_dois_workers_constroem_a_mesma_chave_e_a_constraint_impede_insert_duplicado():
    previous = _observation(action="WAIT")
    current = _observation(action="BUY")

    def evaluate(_worker_number: int) -> str:
        return _events(previous, current)[0].deduplication_key

    with ThreadPoolExecutor(max_workers=8) as executor:
        keys = list(executor.map(evaluate, range(64)))

    assert len(set(keys)) == 1
    assert ("deduplication_key",) in _unique_column_sets(InvestmentAlert)


def test_evaluation_key_deduplica_retry_no_mesmo_dia_e_nao_uma_nova_janela():
    morning = datetime(2026, 8, 26, 8, 0, tzinfo=UTC)
    evening = datetime(2026, 8, 26, 23, 59, tzinfo=UTC)
    next_day = datetime(2026, 8, 27, 0, 0, tzinfo=UTC)
    assert build_evaluation_key(37, morning) == build_evaluation_key(37, evening)
    assert build_evaluation_key(37, morning) != build_evaluation_key(37, next_day)
    assert build_evaluation_key(37, morning) != build_evaluation_key(38, morning)


def test_cooldown_suprime_equivalente_mas_high_materialmente_novo_pode_ultrapassar():
    previous = _observation(action="WAIT")
    current = _observation(action="BUY")
    candidate = _events(previous, current)[0]
    last_created = NOW
    within = NOW.replace(minute=NOW.minute + 1)

    assert cooldown_allows(
        candidate=candidate,
        last_created_at=None,
        last_deduplication_key=None,
        now=within,
        cooldown_minutes=180,
    )
    assert not cooldown_allows(
        candidate=candidate,
        last_created_at=last_created,
        last_deduplication_key=candidate.deduplication_key,
        now=within,
        cooldown_minutes=180,
    )

    materially_new = _events(_observation(action="AVOID"), current)[0]
    assert materially_new.severity == SEVERITY_HIGH
    assert materially_new.deduplication_key != candidate.deduplication_key
    assert cooldown_allows(
        candidate=materially_new,
        last_created_at=last_created,
        last_deduplication_key=candidate.deduplication_key,
        now=within,
        cooldown_minutes=180,
    )


def test_cooldown_medio_so_libera_no_limite_exato():
    candidate = _events(
        _observation(score="70"),
        _observation(score="75"),
        alert_on_action_change=False,
        alert_on_confidence_change=False,
        alert_on_risk_change=False,
        alert_on_new_opportunity=False,
    )[0]
    from datetime import timedelta

    assert not cooldown_allows(
        candidate=candidate,
        last_created_at=NOW,
        last_deduplication_key="outra-chave",
        now=NOW + timedelta(minutes=179, seconds=59),
        cooldown_minutes=180,
    )
    assert cooldown_allows(
        candidate=candidate,
        last_created_at=NOW,
        last_deduplication_key="outra-chave",
        now=NOW + timedelta(minutes=180),
        cooldown_minutes=180,
    )


def test_migration_fase37_e_aditiva_encadeada_na_fase36():
    versions_dir = Path(__file__).parents[1] / "alembic" / "versions"
    candidates = [
        path
        for path in versions_dir.glob("*.py")
        if "alert" in path.name.lower() and "investment" in path.name.lower()
    ]
    assert len(candidates) == 1, "A Fase 37 deve possuir uma única migration aditiva de alertas"

    spec = importlib.util.spec_from_file_location("fase37_alerts_migration", candidates[0])
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.down_revision == "0016_decision_performance"
    assert str(migration.revision).startswith("0017")
    source = candidates[0].read_text(encoding="utf-8")
    for table in (
        "investment_alert_subscriptions",
        "investment_alert_states",
        "investment_alerts",
    ):
        assert f'"{table}"' in source
    assert "uq_alert_subscriptions_user_asset" in source
    assert "uq_investment_alerts_deduplication_key" in source
    assert "investment_decision_audits.decision_id" in source
