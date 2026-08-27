from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint

from backend.app.core.celery import celery_app
from backend.app.investment_decisions import versions as decision_versions
from backend.app.investment_performance import repository
from backend.app.investment_performance.models import InvestmentDecisionPerformance
from backend.app.investment_performance.tasks import evaluate_due_investment_performance
from backend.app.investment_performance import tasks as performance_tasks
from backend.app.main import app


ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = ROOT / "backend" / "app" / "investment_performance"
MIGRATION = ROOT / "backend" / "alembic" / "versions" / "0016_create_investment_decision_performance.py"


def test_modelo_tem_fk_restrict_unique_decision_horizon_e_indice_temporal():
    table = InvestmentDecisionPerformance.__table__
    uniques = [constraint for constraint in table.constraints if isinstance(constraint, UniqueConstraint)]
    assert any(
        constraint.name == "uq_decision_performance_decision_horizon"
        and [column.name for column in constraint.columns] == ["decision_id", "horizon"]
        for constraint in uniques
    )
    foreign_keys = [
        constraint for constraint in table.constraints if isinstance(constraint, ForeignKeyConstraint)
    ]
    assert len(foreign_keys) == 1
    assert foreign_keys[0].name == "fk_decision_performance_decision_id"
    assert foreign_keys[0].ondelete == "RESTRICT"
    assert list(foreign_keys[0].elements)[0].target_fullname == (
        "investment_decision_audits.decision_id"
    )
    assert {
        (index.name, tuple(column.name for column in index.columns)) for index in table.indexes
    } == {
        (
            "ix_decision_performance_horizon_evaluated",
            ("horizon", "evaluated_at"),
        )
    }
    assert "user_id" not in table.columns


def test_migration_0016_e_aditiva_e_encadeada_na_fase35():
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
    assert assignments["revision"] == "0016_decision_performance"
    assert assignments["down_revision"] == "0015_decision_audits"
    upgrade = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade"
    )
    calls = {
        node.func.attr
        for node in ast.walk(upgrade)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert calls <= {"create_table", "create_index", "Column", "ForeignKeyConstraint", "PrimaryKeyConstraint", "UniqueConstraint", "Integer", "String", "Numeric", "DateTime", "JSON", "now"}
    assert "create_table" in calls
    assert "create_index" in calls
    assert not ({"drop_table", "drop_column", "alter_column", "execute"} & calls)


def test_repositorio_filtra_auditoria_valida_e_owner_na_mesma_query():
    statement = repository.valid_decision_statement(
        user_id=36,
        asset="petr4",
        action="BUY",
        risk_level="LOW",
        investor_profile="MODERATE",
        rule_version="rule-v1",
        recommendation_engine_version="engine-v1",
    )
    compiled = str(statement)
    assert "user_id" in compiled
    assert "status" in compiled
    assert "recommendation" in compiled
    assert "asset" in compiled
    assert "risk_level" in compiled
    assert "investor_profile" in compiled
    assert "rule_version" in compiled
    assert "recommendation_engine_version" in compiled


class _ScalarResult:
    def scalar_one_or_none(self):
        return None


class _CaptureSession:
    def __init__(self):
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _ScalarResult()


@pytest.mark.asyncio
async def test_lookup_de_detalhe_combina_owner_decision_id_e_validade():
    session = _CaptureSession()
    result = await repository.get_owned_decision(
        session,
        user_id=36,
        decision_id="36000000-0000-4000-8000-000000000001",
    )
    assert result is None
    statement = str(session.statements[0])
    assert "user_id" in statement
    assert "decision_id" in statement
    assert "status" in statement


def test_persistencia_e_idempotente_no_banco_e_nao_atualiza_auditoria():
    source = inspect.getsource(repository)
    assert "on_conflict_do_nothing" in source
    assert "InvestmentDecisionPerformance.decision_id" in source
    assert "InvestmentDecisionPerformance.horizon" in source
    assert "update(" not in source
    assert "delete(" not in source
    assert "session.add" not in source


def test_modulo_nao_importa_recommendation_engine_trend_ml_ou_trading():
    forbidden_prefixes = (
        "backend.app.intelligence",
        "backend.trading",
    )
    for path in MODULE_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not any(
            imported.startswith(forbidden_prefixes) for imported in imports
        ), f"import proibido em {path.name}: {imports}"


def test_endpoints_da_fase36_sao_exclusivamente_get_e_autenticados_por_dependencia():
    schema_paths = app.openapi()["paths"]
    for path in {
        "/api/v1/investments/performance",
        "/api/v1/investments/decisions/{decision_id}/performance",
    }:
        assert set(schema_paths[path]) == {"get"}
        assert schema_paths[path]["get"]["security"] == [{"HTTPBearer": []}]


def test_celery_reutiliza_worker_beat_e_fila_intelligence():
    includes = set(celery_app.conf.include or [])
    assert "backend.app.investment_performance.tasks" in includes
    assert celery_app.conf.task_routes["investment_performance.evaluate_due"] == {
        "queue": "intelligence"
    }
    schedule = celery_app.conf.beat_schedule["investment-performance-evaluate-daily"]
    assert schedule["task"] == "investment_performance.evaluate_due"
    assert schedule["options"] == {"queue": "intelligence"}
    assert evaluate_due_investment_performance.name == "investment_performance.evaluate_due"


def test_fase36_nao_incrementa_versoes_financeiras_da_fase35():
    assert decision_versions.RECOMMENDATION_ENGINE_VERSION == "budget-advisor-v1"
    assert decision_versions.RULE_VERSION == "investment-decision-presentation-v1"
    assert decision_versions.SCORE_VERSION == "vinance_score_v1"
    assert decision_versions.GUARDRAIL_VERSION == "vinance_guardrail_v1"
    assert decision_versions.TREND_VERSION == "vinance_trend_v1"


@pytest.mark.asyncio
async def test_task_registra_contagens_sem_chaves_reservadas_do_logging(monkeypatch):
    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def rollback(self):
            raise AssertionError("não deve fazer rollback em sucesso")

    async def fake_process(_session):
        return {
            "status": "SUCCESS",
            "eligible": 3,
            "created": 2,
            "pending_prices": 1,
        }

    monkeypatch.setattr(performance_tasks, "AsyncSessionLocal", Session)
    monkeypatch.setattr(performance_tasks, "process_due_evaluations", fake_process)
    result = await performance_tasks._evaluate_due_investment_performance()
    assert result["created"] == 2
