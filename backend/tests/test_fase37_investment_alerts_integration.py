from __future__ import annotations

import ast
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from backend.app.core.celery import celery_app
from backend.app.core.celery import _configure_structured_celery_logging
from backend.app.core.logging import StructuredFormatter
from backend.app.investment_alerts import repository, service, tasks
from backend.app.investment_alerts.evaluator import build_evaluation_key
from backend.app.investment_alerts.models import InvestmentAlertState
from backend.app.investment_alerts.rules import ALERT_RULE_VERSION
from backend.app.investment_alerts.tasks import evaluate_investment_alert_subscriptions
from backend.app.investment_decisions.models import InvestmentDecisionAudit
from backend.app.main import app


ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = ROOT / "backend" / "app" / "investment_alerts"
MIGRATION = ROOT / "backend" / "alembic" / "versions" / "0017_create_investment_alerts.py"
UTC_NOW = datetime(2026, 8, 27, 1, 15, tzinfo=timezone.utc)
SOURCE_DECISION_ID = "37000000-0000-4000-8000-000000000001"


def _subscription(**overrides):
    values = {
        "id": 7,
        "user_id": 37,
        "asset": "GARE11",
        "market": "FII",
        "budget": Decimal("300"),
        "investor_profile": "CONSERVATIVE",
        "include_warnings": False,
        "trend_filter": None,
        "source_decision_id": SOURCE_DECISION_ID,
        "enabled": True,
        "alert_on_action_change": True,
        "alert_on_score_change": True,
        "alert_on_confidence_change": True,
        "alert_on_risk_change": True,
        "alert_on_new_opportunity": True,
        "minimum_score_delta": Decimal("5"),
        "minimum_confidence_delta": Decimal("10"),
        "cooldown_minutes": 180,
        "rule_version": ALERT_RULE_VERSION,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _decision(**overrides):
    values = {
        "decision_id": SOURCE_DECISION_ID,
        "correlation_id": "37000000-0000-4000-8000-000000000002",
        "user_id": 37,
        "created_at": UTC_NOW,
        "asset": "GARE11",
        "market": "FII",
        "budget": Decimal("300"),
        "investor_profile": "CONSERVATIVE",
        "recommendation": "WAIT",
        "recommendation_score": Decimal("70"),
        "confidence": Decimal("80"),
        "risk_level": "LOW",
        "trend": "SIDEWAYS",
        "request_parameters": {
            "budget": "300",
            "market": "FII",
            "profile": "CONSERVATIVE",
            "include_warnings": False,
            "trend_filter": None,
        },
        "status": "SUCCESS",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class _Session:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class _SessionFactory:
    def __init__(self):
        self.sessions: list[_Session] = []

    def __call__(self):
        session = _Session()
        self.sessions.append(session)
        return session


def test_migration_0017_e_exclusivamente_aditiva_e_encadeada_na_fase36():
    source = MIGRATION.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
    }
    assert assignments["revision"] == "0017_investment_alerts"
    assert assignments["down_revision"] == "0016_decision_performance"
    upgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade")
    called_attributes = {
        node.func.attr
        for node in ast.walk(upgrade)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "create_table" in called_attributes
    assert "create_index" in called_attributes
    assert not ({"drop_table", "drop_column", "alter_column", "execute"} & called_attributes)
    assert "CASCADE" in source
    assert "SET NULL" in source
    assert "RESTRICT" in source


def test_modulo_nao_importa_trading_ml_ou_cria_scheduler_paralelo():
    forbidden_prefixes = ("backend.trading", "backend.app.intelligence.ml")
    for path in MODULE_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not any(item.startswith(forbidden_prefixes) for item in imports), path.name
    assert not (MODULE_DIR / "scheduler.py").exists()


def test_rotas_da_fase37_estao_no_api_v1_e_todas_exigem_autenticacao():
    paths = {
        "/api/v1/investments/alert-subscriptions": {"GET", "POST"},
        "/api/v1/investments/alert-subscriptions/{subscription_id}": {"PATCH", "DELETE"},
        "/api/v1/investments/alerts": {"GET"},
        "/api/v1/investments/alerts/metrics": {"GET"},
        "/api/v1/investments/alerts/{alert_id}": {"GET"},
        "/api/v1/investments/alerts/{alert_id}/read": {"PATCH"},
    }
    schema_paths = app.openapi()["paths"]
    methods_by_path = {
        path: {method.upper() for method in schema_paths[path]}
        for path in paths
    }
    assert methods_by_path == paths
    for path, methods in paths.items():
        for method in methods:
            assert schema_paths[path][method.lower()]["security"] == [{"HTTPBearer": []}]


def test_celery_reutiliza_worker_beat_existentes_e_fila_intelligence_em_frequencia_diaria():
    assert "backend.app.investment_alerts.tasks" in set(celery_app.conf.include or [])
    assert celery_app.conf.task_routes["investment_alerts.evaluate_subscriptions"] == {
        "queue": "intelligence"
    }
    schedule = celery_app.conf.beat_schedule[
        "investment-alerts-evaluate-daily-after-intelligence"
    ]
    assert schedule["task"] == "investment_alerts.evaluate_subscriptions"
    assert schedule["options"] == {"queue": "intelligence"}
    assert str(schedule["schedule"]) == "<crontab: 10 22 * * * (m/h/dM/MY/d)>"
    assert evaluate_investment_alert_subscriptions.name == "investment_alerts.evaluate_subscriptions"


def test_celery_aplica_formatter_estruturado_com_redacao_nos_handlers():
    logger = logging.Logger("fase37.celery")
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    _configure_structured_celery_logging(logger)
    assert isinstance(handler.formatter, StructuredFormatter)


def test_repositorio_combina_owner_em_todas_as_operacoes_expostas():
    source = (MODULE_DIR / "repository.py").read_text(encoding="utf-8")
    for function_name in (
        "get_owned_subscription",
        "get_owned_subscription_by_asset",
        "list_owned_subscriptions",
        "list_owned_alerts",
        "get_owned_alert",
        "mark_owned_alert_read",
    ):
        function = next(
            node
            for node in ast.parse(source).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
        )
        segment = ast.get_source_segment(source, function) or ""
        assert "user_id" in segment


def test_concorrencia_usa_lock_de_estado_e_insert_atomico_com_on_conflict():
    source = (MODULE_DIR / "repository.py").read_text(encoding="utf-8")
    assert ".with_for_update(of=InvestmentAlertState)" in source
    assert "pg_advisory_xact_lock" in source
    assert "on_conflict_do_nothing" in source
    assert "InvestmentAlert.deduplication_key" in source


@pytest.mark.asyncio
async def test_criacao_de_subscription_deriva_dados_da_fase35_e_semeia_estado(monkeypatch):
    source = _decision()
    captured = {}

    async def no_lock(*_args, **_kwargs):
        return None

    async def active_count(*_args, **_kwargs):
        return 0

    async def owned_source(*_args, **kwargs):
        captured["source_lookup"] = kwargs
        return source

    async def persist(_session, *, subscription, state):
        subscription.id = 7
        state.subscription_id = 7
        captured["subscription"] = subscription
        captured["state"] = state
        return subscription

    monkeypatch.setattr(service, "lock_user_subscription_quota", no_lock)
    monkeypatch.setattr(service, "count_active_subscriptions", active_count)
    monkeypatch.setattr(service, "get_owned_source_decision", owned_source)
    monkeypatch.setattr(service, "create_subscription_with_state", persist)

    payload = service.SubscriptionCreate(asset="gare11", source_decision_id=SOURCE_DECISION_ID)
    created = await service.create_monitoring_subscription(
        object(), user_id=37, payload=payload
    )
    assert created.asset == "GARE11"
    assert created.market == source.market
    assert created.budget == source.budget
    assert created.investor_profile == source.investor_profile
    assert captured["source_lookup"]["user_id"] == 37
    state = captured["state"]
    assert state.last_decision_id == SOURCE_DECISION_ID
    assert state.last_action == "WAIT"
    assert state.last_score == Decimal("70")
    assert state.last_confidence == Decimal("80")
    assert state.last_risk_level == "LOW"


def test_payload_focado_preserva_resultado_do_engine_e_apenas_seleciona_o_ativo_monitorado():
    best = {"ticker": "CPTS11", "recommendation_score": Decimal("90")}
    monitored = {"ticker": "GARE11", "recommendation_score": Decimal("82")}
    payload = {"budget": Decimal("300"), "best_recommendation": best, "alternatives": [monitored]}
    focused, found = service._focused_payload(payload, "GARE11")
    assert found is True
    assert focused["best_recommendation"] is monitored
    assert focused["alternatives"] == [best]
    assert payload["best_recommendation"] is best
    missing, found = service._focused_payload(payload, "NAOEXISTE")
    assert found is False
    assert missing["best_recommendation"] is None


@pytest.mark.asyncio
async def test_automacao_usa_fluxo_oficial_e_persiste_decisao_auditavel_fase35(monkeypatch):
    calls = {}
    payload = {
        "budget": Decimal("300"),
        "market": "FII",
        "profile": "CONSERVATIVE",
        "best_recommendation": {
            "ticker": "CPTS11",
            "market": "FII",
            "status": "APPROVED",
            "risk_level": "LOW",
            "recommendation_score": Decimal("90"),
            "confidence_score": Decimal("91"),
            "trend_label": "UPTREND",
        },
        "alternatives": [
            {
                "ticker": "GARE11",
                "market": "FII",
                "status": "APPROVED",
                "risk_level": "LOW",
                "recommendation_score": Decimal("82"),
                "confidence_score": Decimal("88"),
                "trend_label": "SIDEWAYS",
                "quantity_possible": 36,
                "invested_amount": Decimal("296.28"),
                "remaining_budget": Decimal("3.72"),
            }
        ],
    }

    async def no_existing(*_args, **_kwargs):
        return None

    async def official_engine(_session, **kwargs):
        calls["engine"] = kwargs
        return payload

    async def persist(_session, record):
        calls["record"] = record
        return record

    monkeypatch.setattr(service, "get_decision_by_id", no_existing)
    monkeypatch.setattr(service, "build_explained_budget_recommendations", official_engine)
    monkeypatch.setattr(service, "persist_decision_audit", persist)
    factory = _SessionFactory()
    record = await service._generate_or_reuse_audited_decision(
        subscription=_subscription(),
        evaluation_key=build_evaluation_key(7, UTC_NOW),
        effective_at=UTC_NOW,
        session_factory=factory,
    )
    assert calls["engine"] == {
        "budget": Decimal("300"),
        "market": "FII",
        "limit": 100,
        "include_warnings": False,
        "profile": "CONSERVATIVE",
        "trend_filter": None,
    }
    assert isinstance(record, InvestmentDecisionAudit)
    assert record.user_id == 37
    assert record.asset == "GARE11"
    assert record.status == "SUCCESS"
    assert record.request_parameters["source"] == "INVESTMENT_ALERT_AUTOMATION"
    assert UUID(record.decision_id)
    assert UUID(record.correlation_id)


@pytest.mark.asyncio
async def test_retry_reutiliza_mesma_decisao_auditada_sem_reexecutar_engine(monkeypatch):
    existing = _decision(decision_id="daedba2f-c709-53b8-a63d-46cdd7251644")

    async def get_existing(*_args, **_kwargs):
        return existing

    async def should_not_run(*_args, **_kwargs):
        raise AssertionError("engine não deve executar em retry da mesma decisão")

    monkeypatch.setattr(service, "get_decision_by_id", get_existing)
    monkeypatch.setattr(service, "build_explained_budget_recommendations", should_not_run)
    result = await service._generate_or_reuse_audited_decision(
        subscription=_subscription(),
        evaluation_key="same-evaluation",
        effective_at=UTC_NOW,
        session_factory=_SessionFactory(),
    )
    assert result is existing


@pytest.mark.asyncio
async def test_falha_do_engine_registra_auditoria_de_erro_sem_fabricar_alerta(monkeypatch):
    captured = {}

    async def no_existing(*_args, **_kwargs):
        return None

    async def fail_engine(*_args, **_kwargs):
        raise RuntimeError("provider indisponível")

    async def fail_open(_session, record):
        captured["record"] = record
        return True

    monkeypatch.setattr(service, "get_decision_by_id", no_existing)
    monkeypatch.setattr(service, "build_explained_budget_recommendations", fail_engine)
    monkeypatch.setattr(service, "persist_decision_audit_fail_open", fail_open)
    with pytest.raises(RuntimeError, match="provider indisponível"):
        await service._generate_or_reuse_audited_decision(
            subscription=_subscription(),
            evaluation_key="failed-evaluation",
            effective_at=UTC_NOW,
            session_factory=_SessionFactory(),
        )
    assert captured["record"].status == "ERROR"
    assert captured["record"].error_code == "ALERT_EVALUATION_ERROR"
    assert captured["record"].recommendation == "NO_RECOMMENDATION"


@pytest.mark.asyncio
async def test_retry_da_mesma_avaliacao_e_interrompido_sob_lock_antes_do_engine(monkeypatch):
    state = SimpleNamespace(
        last_evaluation_key=build_evaluation_key(7, UTC_NOW),
        duplicates_prevented_count=2,
    )

    async def locked_pair(*_args, **_kwargs):
        return _subscription(), state

    async def should_not_run(*_args, **_kwargs):
        raise AssertionError("engine não deve executar em retry concluído")

    monkeypatch.setattr(service, "get_subscription_state_for_update", locked_pair)
    monkeypatch.setattr(service, "_generate_or_reuse_audited_decision", should_not_run)
    factory = _SessionFactory()
    result = await service.evaluate_subscription(
        subscription_id=7,
        effective_at=UTC_NOW,
        session_factory=factory,
    )
    assert result["status"] == "SKIPPED_DUPLICATE"
    assert result["alerts_created"] == 0
    assert state.duplicates_prevented_count == 3
    assert factory.sessions[0].commits == 1


@pytest.mark.asyncio
async def test_avaliacao_persiste_alerta_e_estado_no_mesmo_commit(monkeypatch):
    state = SimpleNamespace(
        last_evaluation_key=None,
        last_decision_id=SOURCE_DECISION_ID,
        last_action="WAIT",
        last_score=Decimal("70"),
        last_confidence=Decimal("80"),
        last_risk_level="LOW",
        last_trend="SIDEWAYS",
        last_checked_at=UTC_NOW,
        evaluations_count=0,
        alerts_generated_count=0,
        cooldown_suppressed_count=0,
        duplicates_prevented_count=0,
    )
    current = _decision(
        decision_id="37000000-0000-4000-8000-000000000099",
        recommendation="BUY",
        recommendation_score=Decimal("82"),
        confidence=Decimal("92"),
        trend="UPTREND",
    )
    inserted_payloads = []

    async def locked_pair(*_args, **_kwargs):
        return _subscription(), state

    async def generated(*_args, **_kwargs):
        return current

    async def no_previous(*_args, **_kwargs):
        return {}

    async def insert(_session, payload):
        inserted_payloads.append(payload)
        return True

    monkeypatch.setattr(service, "get_subscription_state_for_update", locked_pair)
    monkeypatch.setattr(service, "_generate_or_reuse_audited_decision", generated)
    monkeypatch.setattr(service, "latest_alerts_by_type", no_previous)
    monkeypatch.setattr(service, "insert_alert_if_absent", insert)
    factory = _SessionFactory()
    result = await service.evaluate_subscription(
        subscription_id=7,
        effective_at=UTC_NOW,
        session_factory=factory,
    )
    assert result["status"] == "SUCCESS"
    assert result["alerts_created"] == 3
    assert {item["alert_type"] for item in inserted_payloads} == {
        "NEW_OPPORTUNITY",
        "SCORE_CHANGE",
        "CONFIDENCE_CHANGE",
    }
    assert all(item["delivery_channel"] == "IN_APP" for item in inserted_payloads)
    assert state.last_decision_id == current.decision_id
    assert state.last_action == "BUY"
    assert state.evaluations_count == 1
    assert state.alerts_generated_count == 3
    assert factory.sessions[0].commits == 1


@pytest.mark.asyncio
async def test_cooldown_suprime_alerta_mas_atualiza_estado_monitorado(monkeypatch):
    state = SimpleNamespace(
        last_evaluation_key=None,
        last_decision_id=SOURCE_DECISION_ID,
        last_action="WAIT",
        last_score=Decimal("70"),
        last_confidence=Decimal("80"),
        last_risk_level="LOW",
        last_trend="SIDEWAYS",
        last_checked_at=UTC_NOW,
        evaluations_count=0,
        alerts_generated_count=0,
        cooldown_suppressed_count=0,
        duplicates_prevented_count=0,
    )
    current = _decision(
        decision_id="37000000-0000-4000-8000-000000000098",
        recommendation_score=Decimal("80"),
    )

    async def locked_pair(*_args, **_kwargs):
        return _subscription(), state

    async def generated(*_args, **_kwargs):
        return current

    async def latest(*_args, **_kwargs):
        return {
            "SCORE_CHANGE": SimpleNamespace(
                created_at=UTC_NOW,
                deduplication_key="outra-ocorrencia",
            )
        }

    async def should_not_insert(*_args, **_kwargs):
        raise AssertionError("alerta em cooldown não deve ser inserido")

    monkeypatch.setattr(service, "get_subscription_state_for_update", locked_pair)
    monkeypatch.setattr(service, "_generate_or_reuse_audited_decision", generated)
    monkeypatch.setattr(service, "latest_alerts_by_type", latest)
    monkeypatch.setattr(service, "insert_alert_if_absent", should_not_insert)
    factory = _SessionFactory()
    result = await service.evaluate_subscription(
        subscription_id=7,
        effective_at=UTC_NOW,
        session_factory=factory,
    )
    assert result["alerts_created"] == 0
    assert result["cooldown_suppressed"] == 1
    assert state.last_decision_id == current.decision_id
    assert state.last_score == Decimal("80")
    assert state.evaluations_count == 1
    assert state.cooldown_suppressed_count == 1
    assert factory.sessions[0].commits == 1


@pytest.mark.asyncio
async def test_ciclo_isola_falha_de_uma_subscription_e_continua_as_demais(monkeypatch):
    async def list_ids(*_args, **_kwargs):
        return [1, 2, 3]

    async def evaluate(*, subscription_id, **_kwargs):
        if subscription_id == 2:
            raise RuntimeError("falha isolada")
        return {
            "status": "SUCCESS",
            "alerts_created": 1,
            "cooldown_suppressed": 0,
            "duplicates_prevented": 0,
            "by_type": {"SCORE_CHANGE": 1},
        }

    errors = []

    async def increment(*_args, **kwargs):
        errors.append(kwargs["subscription_id"])

    monkeypatch.setattr(service, "list_active_subscription_ids", list_ids)
    monkeypatch.setattr(service, "evaluate_subscription", evaluate)
    monkeypatch.setattr(service, "increment_state_error", increment)
    result = await service.evaluate_active_subscriptions(
        effective_at=UTC_NOW,
        session_factory=_SessionFactory(),
    )
    assert result["evaluated"] == 2
    assert result["alerts_generated"] == 2
    assert result["errors"] == 1
    assert result["by_type"] == {"SCORE_CHANGE": 2}
    assert errors == [2]


def test_logs_estruturados_expoem_ids_operacionais_sem_bearer_token():
    formatter = StructuredFormatter()
    record = logging.LogRecord(
        name="backend.app.investment_alerts.service",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Bearer token-ultrassecreto",
        args=(),
        exc_info=None,
    )
    record.user_id = 37
    record.subscription_id = 7
    record.decision_id = SOURCE_DECISION_ID
    record.alert_id = "37000000-0000-4000-8000-000000000002"
    record.alert_type = "NEW_OPPORTUNITY"
    record.severity = "HIGH"
    payload = json.loads(formatter.format(record))
    serialized = json.dumps(payload)
    assert payload["subscription_id"] == 7
    assert payload["alert_type"] == "NEW_OPPORTUNITY"
    assert "token-ultrassecreto" not in serialized
    assert "Bearer [REDACTED]" in serialized


@pytest.mark.asyncio
async def test_task_publica_resumo_sem_executar_ordens(monkeypatch):
    async def fake_cycle():
        return {
            "status": "SUCCESS",
            "evaluated": 2,
            "alerts_generated": 1,
            "cooldown_suppressed": 1,
            "duplicates_prevented": 1,
            "errors": 0,
        }

    monkeypatch.setattr(tasks, "evaluate_active_subscriptions", fake_cycle)
    result = await fake_cycle()
    assert result["alerts_generated"] == 1
    task_source = (MODULE_DIR / "tasks.py").read_text(encoding="utf-8").lower()
    assert "trading" not in task_source
    assert "execute_order" not in task_source
    assert "paper" not in task_source
