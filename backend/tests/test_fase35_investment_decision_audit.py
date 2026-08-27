from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.core.logging import StructuredFormatter
from backend.app.intelligence import router as intelligence_router
from backend.app.investment_decisions import router as decision_router
from backend.app.investment_decisions.models import InvestmentDecisionAudit
from backend.app.investment_decisions.service import (
    ACTION_AVOID,
    ACTION_BUY,
    ACTION_WAIT,
    STATUS_SUCCESS,
    _history_filters,
    build_decision_audit,
    canonical_uuid,
    derive_presented_action,
    get_decision_metrics,
    get_owned_decision,
    list_decision_history,
    normalize_asset_filter,
    persist_decision_audit,
    persist_decision_audit_fail_open,
    sanitize_snapshot,
)
from backend.app.main import app

DECISION_ID = "35000000-0000-4000-8000-000000000001"
CORRELATION_ID = "35000000-0000-4000-8000-000000000002"


def _payload(**overrides):
    best = {
        "ticker": "GARE11",
        "market": "FII",
        "price": Decimal("8.23"),
        "quantity_possible": 36,
        "invested_amount": Decimal("296.28"),
        "remaining_budget": Decimal("3.72"),
        "profile": "CONSERVATIVE",
        "status": "APPROVED",
        "risk_level": "LOW",
        "recommendation_score": Decimal("87.3"),
        "confidence_score": Decimal("100"),
        "confidence_label": "HIGH",
        "trend_label": "UPTREND",
        "momentum_score": Decimal("72"),
        "appreciation_signal": "HIGH",
        "recommendation_components_json": {"fundamental": "84"},
        "reasons_json": {"blocked": [], "warnings": [], "summary": ["Aprovado"]},
        "score_breakdown": {"recommendation_score": Decimal("87.3"), "risk_score": Decimal("90")},
        "relative_position": {"rank": 1, "total_candidates": 2},
        "executive_summary": "Resumo seguro.",
        "why_recommended": ["Score consistente"],
    }
    best.update(overrides)
    return {
        "budget": Decimal("300"),
        "market": "FII",
        "profile": "CONSERVATIVE",
        "best_recommendation": best,
        "alternatives": [{**best, "ticker": "CPTS11", "recommendation_score": Decimal("81")}],
        "disclaimer": "Sem garantia de retorno.",
    }


def _record(**overrides):
    values = {
        "decision_id": DECISION_ID,
        "correlation_id": CORRELATION_ID,
        "user_id": 35,
        "request_parameters": {"budget": Decimal("300"), "market": "FII", "profile": "CONSERVATIVE", "explain": True},
        "payload": _payload(),
        "latency_ms": 41,
        "status": STATUS_SUCCESS,
        "created_at": datetime(2026, 8, 25, 14, 30, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return build_decision_audit(**values)


def test_uuid_preserva_valido_e_substitui_entrada_arbitraria():
    assert canonical_uuid(f"  {DECISION_ID}  ") == DECISION_ID
    generated = canonical_uuid("../../Bearer segredo")
    assert str(UUID(generated)) == generated
    assert generated != DECISION_ID


def test_novas_decisoes_recebem_ids_unicos():
    assert canonical_uuid() != canonical_uuid()


def test_snapshot_remove_segredos_recursivamente_e_serializa_tipos():
    snapshot = sanitize_snapshot(
        {
            "budget": Decimal("300.00"),
            "authorization": "Bearer token-ultrassecreto",
            "nested": {
                "password": "senha",
                "api-key": "chave",
                "safe": "ok",
                "non_finite": float("nan"),
            },
            "text": "Bearer token-em-valor",
        }
    )
    serialized = json.dumps(snapshot, allow_nan=False)
    assert snapshot["budget"] == "300.00"
    assert snapshot["nested"] == {"safe": "ok", "non_finite": None}
    assert snapshot["text"] == "[REDACTED]"
    assert "token-ultrassecreto" not in serialized
    assert "senha" not in serialized
    assert "chave" not in serialized


def test_audit_record_congela_snapshot_campos_versoes_e_latencia():
    payload = _payload()
    record = _record(payload=payload)
    payload["best_recommendation"]["ticker"] = "ALTERADO11"

    assert record.decision_id == DECISION_ID
    assert record.asset == "GARE11"
    assert record.recommendation == ACTION_BUY
    assert record.quantity == 36
    assert record.invested_amount == Decimal("296.28")
    assert record.remaining_amount == Decimal("3.72")
    assert record.guardrail_status == "APPROVED"
    assert record.guardrail_reasons["summary"] == ["Aprovado"]
    assert record.score_snapshot["recommendation_score"] == "87.3"
    assert record.score_snapshot["recommendation_components"] == {"fundamental": "84"}
    assert record.input_snapshot["selected_candidate"]["ticker"] == "GARE11"
    assert record.response_snapshot["best_recommendation"]["ticker"] == "GARE11"
    assert record.snapshot_schema_version == "investment-decision-audit-v1"
    assert record.rule_version == "investment-decision-presentation-v1"
    assert record.recommendation_engine_version == "budget-advisor-v1"
    assert record.score_version == "vinance_score_v1"
    assert record.guardrail_version == "vinance_guardrail_v1"
    assert record.trend_version == "vinance_trend_v1"
    assert record.latency_ms == 41


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"risk_level": "HIGH"}, ACTION_AVOID),
        ({"trend_label": "SIDEWAYS"}, ACTION_WAIT),
        ({"trend_label": "DOWNTREND"}, ACTION_WAIT),
        ({"status": "APPROVED", "risk_level": "LOW", "trend_label": "UPTREND"}, ACTION_BUY),
    ],
)
def test_acao_auditada_preserva_classificacao_visual_existente(overrides, expected):
    assert derive_presented_action(_payload(**overrides)["best_recommendation"]) == expected


def test_zero_explicito_nao_e_substituido_por_fallback_do_decision_card():
    best = _payload(recommendation_score=0, decision_card={"recommendation_score": 99, "confidence_score": 99})["best_recommendation"]
    assert derive_presented_action(best) == ACTION_WAIT
    assert _record(payload={"budget": 300, "best_recommendation": best, "alternatives": []}).recommendation_score == 0


def test_fallback_e_error_sao_registrados_sem_mudar_payload():
    payload = _payload(trend_method="price_history_fallback")
    record = _record(payload=payload, latency_ms=-1, error_code="SAFE_CODE")
    assert record.fallback_used is True
    assert record.error_code == "SAFE_CODE"
    assert record.latency_ms == 0


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return list(self.value or [])


class _PersistSession:
    def __init__(self, existing=None, fail=False):
        self.existing = existing
        self.fail = fail
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, _statement):
        if self.fail:
            raise RuntimeError("database unavailable")
        return _ScalarResult(self.existing)

    def add(self, record):
        self.added.append(record)
        self.existing = record

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_mesma_decisao_nao_duplica_persistencia():
    session = _PersistSession()
    record = _record()
    assert await persist_decision_audit(session, record) is record
    assert await persist_decision_audit(session, _record()) is record
    assert len(session.added) == 1
    assert session.commits == 1


@pytest.mark.asyncio
async def test_colisao_de_decision_id_entre_usuarios_nao_reaproveita_registro():
    session = _PersistSession(existing=_record(user_id=99))
    with pytest.raises(ValueError, match="collision"):
        await persist_decision_audit(session, _record(user_id=35))


@pytest.mark.asyncio
async def test_falha_de_persistencia_faz_rollback_e_retorna_fail_open():
    session = _PersistSession(fail=True)
    assert await persist_decision_audit_fail_open(session, _record()) is False
    assert session.rollbacks == 1


def test_filtro_de_ativo_rejeita_injection_e_queries_incluem_user_id():
    with pytest.raises(ValueError, match="asset inválido"):
        normalize_asset_filter("GARE11' OR 1=1 --")
    filters = _history_filters(user_id=35, asset="gare11", recommendation="BUY", risk_level="LOW")
    expression = " AND ".join(str(item) for item in filters)
    assert "user_id" in expression
    assert "asset" in expression
    assert "recommendation" in expression
    assert "risk_level" in expression


class _QueryResult:
    def __init__(self, *, scalar=None, rows=None, mapping=None):
        self.scalar = scalar
        self.rows = rows or []
        self.mapping = mapping

    def scalar_one(self):
        return self.scalar

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return self

    def mappings(self):
        return self

    def one(self):
        return self.mapping

    def all(self):
        return self.rows


class _QuerySession:
    def __init__(self, results):
        self.results = list(results)
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_historico_pagina_ordena_e_filtra_por_owner():
    row = _record()
    session = _QuerySession([_QueryResult(scalar=1), _QueryResult(rows=[row])])
    result = await list_decision_history(session, user_id=35, page=1, page_size=10, asset="GARE11")
    assert result["items"] == [row]
    assert result["total"] == 1
    assert result["total_pages"] == 1
    assert "created_at DESC" in str(session.statements[1])
    assert "user_id" in str(session.statements[1])


@pytest.mark.asyncio
async def test_detalhe_aplica_decision_id_e_owner_na_mesma_query():
    session = _QuerySession([_QueryResult(scalar=None)])
    assert await get_owned_decision(session, user_id=77, decision_id=DECISION_ID) is None
    statement = str(session.statements[0])
    assert "decision_id" in statement
    assert "user_id" in statement


@pytest.mark.asyncio
async def test_metricas_agregam_apenas_query_com_owner():
    summary = {
        "total_decisions": 4,
        "comprar": 1,
        "aguardar": 1,
        "evitar": 1,
        "errors": 1,
        "fallbacks": 1,
        "average_latency_ms": Decimal("25.5"),
        "p95_latency_ms": Decimal("49"),
    }
    session = _QuerySession(
        [
            _QueryResult(mapping=summary),
            _QueryResult(rows=[("GARE11", 3)]),
            _QueryResult(rows=[("CONSERVATIVE", 4)]),
            _QueryResult(rows=[("LOW", 3), ("HIGH", 1)]),
        ]
    )
    metrics = await get_decision_metrics(session, user_id=35)
    assert metrics["total_decisions"] == 4
    assert metrics["p95_latency_ms"] == 49
    assert metrics["by_profile"] == {"CONSERVATIVE": 4}
    assert metrics["top_assets"] == [{"asset": "GARE11", "total": 3}]
    assert all("user_id" in str(statement) for statement in session.statements)


async def _fake_user():
    return User(id=35, email="fase35@test.local", full_name="Fase 35", hashed_password="x", is_active=True)


async def _fake_session():
    yield object()


def _overrides():
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_session] = _fake_session
    return previous


def _restore(previous):
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def test_historico_anonimo_retorna_401():
    previous = dict(app.dependency_overrides)
    try:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_session] = _fake_session
        with TestClient(app) as client:
            response = client.get("/api/v1/investments/decisions")
        assert response.status_code == 401
    finally:
        _restore(previous)


def test_history_endpoint_encaminha_owner_paginacao_e_filtros(monkeypatch):
    captured = {}

    async def fake_history(_session, **kwargs):
        captured.update(kwargs)
        return {"items": [], "page": kwargs["page"], "page_size": kwargs["page_size"], "total": 0, "total_pages": 0}

    monkeypatch.setattr(decision_router, "list_decision_history", fake_history)
    previous = _overrides()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/investments/decisions",
                params={"page": 2, "page_size": 5, "asset": "GARE11", "action": "BUY", "risk_level": "LOW"},
            )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert captured["user_id"] == 35
        assert captured["page"] == 2
        assert captured["asset"] == "GARE11"
        assert captured["recommendation"] == "BUY"
    finally:
        _restore(previous)


def test_id_invalido_e_decisao_de_outro_usuario_retornam_mesmo_404(monkeypatch):
    async def not_owned(*_args, **_kwargs):
        return None

    monkeypatch.setattr(decision_router, "get_owned_decision", not_owned)
    previous = _overrides()
    try:
        with TestClient(app) as client:
            invalid = client.get("/api/v1/investments/decisions/not-a-uuid")
            foreign = client.get(f"/api/v1/investments/decisions/{DECISION_ID}")
        assert invalid.status_code == foreign.status_code == 404
        assert invalid.json()["error"] == foreign.json()["error"] == "Decisão não encontrada"
    finally:
        _restore(previous)


def test_budget_advisor_preserva_ids_e_payload_financeiro(monkeypatch):
    captured = {}

    async def fake_engine(_session, **_kwargs):
        return _payload()

    async def fake_persist(_session, record):
        captured["record"] = record
        return True

    monkeypatch.setattr(intelligence_router, "build_explained_budget_recommendations", fake_engine)
    monkeypatch.setattr(intelligence_router, "persist_decision_audit_fail_open", fake_persist)
    previous = _overrides()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/intelligence/budget-advisor",
                params={"budget": 300, "market": "FII", "profile": "CONSERVATIVE", "explain": "true"},
                headers={"X-Decision-ID": DECISION_ID, "X-Correlation-ID": CORRELATION_ID},
            )
        body = response.json()
        assert response.status_code == 200
        assert body["decision_id"] == response.headers["x-decision-id"] == DECISION_ID
        assert body["correlation_id"] == response.headers["x-correlation-id"] == CORRELATION_ID
        assert body["budget"] == 300
        assert body["best_recommendation"]["ticker"] == "GARE11"
        assert body["decision_action"] == "BUY"
        assert body["audit_status"] == "PERSISTED"
        assert captured["record"].user_id == 35
        assert captured["record"].response_snapshot["best_recommendation"]["ticker"] == "GARE11"
    finally:
        _restore(previous)


def test_reconsulta_gera_novo_decision_id_e_falha_de_auditoria_nao_muda_resultado(monkeypatch):
    async def fake_engine(_session, **_kwargs):
        return _payload()

    async def failed_audit(_session, _record):
        return False

    monkeypatch.setattr(intelligence_router, "build_explained_budget_recommendations", fake_engine)
    monkeypatch.setattr(intelligence_router, "persist_decision_audit_fail_open", failed_audit)
    previous = _overrides()
    try:
        with TestClient(app) as client:
            first = client.get("/api/intelligence/budget-advisor", params={"budget": 300, "explain": "true"})
            second = client.get("/api/intelligence/budget-advisor", params={"budget": 300, "explain": "true"})
        assert first.status_code == second.status_code == 200
        assert first.json()["decision_id"] != second.json()["decision_id"]
        assert first.json()["best_recommendation"] == second.json()["best_recommendation"]
        assert first.json()["audit_status"] == second.json()["audit_status"] == "FAILED"
    finally:
        _restore(previous)


def test_formatter_estruturado_inclui_ids_e_redige_bearer():
    record = logging.LogRecord(
        name="fase35",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request Bearer token-super-secreto completed",
        args=(),
        exc_info=None,
    )
    record.decision_id = DECISION_ID
    record.correlation_id = CORRELATION_ID
    record.user_id = 35
    record.latency_ms = 41
    output = StructuredFormatter().format(record)
    parsed = json.loads(output)
    assert parsed["decision_id"] == DECISION_ID
    assert parsed["correlation_id"] == CORRELATION_ID
    assert parsed["latency_ms"] == 41
    assert "token-super-secreto" not in output
    assert "Bearer [REDACTED]" in output
