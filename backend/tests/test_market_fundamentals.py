from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from backend.app.core.database import Base, get_session
from backend.app.main import app
from backend.app.market import service
from backend.app.market.models import AcaoFundamental, CriptoFundamental, FiiFundamental
from backend.app.market.schemas import FiiFundamentalListResponse


def _stamp():
    return datetime(2026, 6, 1, tzinfo=timezone.utc)


async def _fake_session():
    yield object()


def _install_overrides():
    app.dependency_overrides[get_session] = _fake_session


def _clear_overrides():
    app.dependency_overrides.clear()


def _fii(**overrides):
    base = {
        "id": 1,
        "ticker": "HGLG11",
        "name": "CSHG Logística",
        "date": date(2026, 6, 1),
        "price": Decimal("160.00"),
        "patrimonio_liq": None,
        "vpa": None,
        "pvp": None,
        "dy_12m": None,
        "dy_3m_acumulado": None,
        "ultimo_rendimento": None,
        "data_ultimo_rend": None,
        "volume_medio_diario": None,
        "liquidez_diaria": None,
        "tipo": None,
        "segmento": "Logística",
        "num_cotistas": None,
        "num_imoveis": None,
        "vacancia_fisica": None,
        "vacancia_financeira": None,
        "gestora": None,
        "administradora": None,
        "taxa_adm": None,
        "taxa_performance": None,
        "source": "test",
        "coletado_em": _stamp(),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_fundamentals_metadata_has_only_market_specific_tables():
    tables = set(Base.metadata.tables.keys())
    assert {"fii_fundamentals", "acoes_fundamentals", "etf_fundamentals", "bdr_fundamentals", "cripto_fundamentals"}.issubset(tables)
    assert "asset_fundamentals" not in tables
    assert not any(table.endswith("_ml_features") for table in tables)


def test_unique_constraints_are_market_specific():
    fii_constraints = {constraint.name for constraint in FiiFundamental.__table__.constraints}
    cripto_constraints = {constraint.name for constraint in CriptoFundamental.__table__.constraints}
    cripto_indexes = {index.name for index in CriptoFundamental.__table__.indexes}
    assert "uq_fii_fundamentals_ticker_date_source" in fii_constraints
    assert "uq_cripto_fundamentals_coin_id_date" not in cripto_constraints
    assert "ix_cripto_fundamentals_coletado_em" in cripto_indexes
    assert "ix_cripto_fundamentals_intraday_lookup" not in cripto_indexes
    assert "ix_cripto_fundamentals_coin_id_coletado_em" in cripto_indexes


@pytest.mark.asyncio
async def test_upsert_normalizes_ticker_and_does_not_duplicate():
    class Result:
        def __init__(self, obj):
            self.obj = obj

        def scalar_one_or_none(self):
            return self.obj

    class FakeSession:
        def __init__(self):
            self.existing = None
            self.added = []
            self.commits = 0
            self.refreshed = []

        async def execute(self, query):
            return Result(self.existing)

        def add(self, obj):
            self.added.append(obj)
            self.existing = obj

        async def commit(self):
            self.commits += 1

        async def refresh(self, obj):
            self.refreshed.append(obj)

    session = FakeSession()
    payload = {"ticker": " hglg11 ", "name": "CSHG Logística", "date": date(2026, 6, 1), "price": Decimal("160"), "source": " Test "}
    first = await service.upsert_fii_fundamental(session, payload)
    second = await service.upsert_fii_fundamental(session, {**payload, "price": Decimal("161")})

    assert first is second
    assert len(session.added) == 1
    assert second.ticker == "HGLG11"
    assert second.source == "test"
    assert second.price == Decimal("161")


def test_fundamental_batch_limit_is_enforced():
    with pytest.raises(ValueError):
        service._ensure_batch_limit([{} for _ in range(501)])


def test_acoes_model_has_expected_indexes():
    indexes = {index.name for index in AcaoFundamental.__table__.indexes}
    assert "ix_acoes_fundamentals_ticker" in indexes
    assert "ix_acoes_fundamentals_setor" in indexes


def test_fundamentals_endpoint_returns_empty_list(monkeypatch):
    _install_overrides()

    async def fake_list(session, **kwargs):
        return [], 0

    monkeypatch.setattr(service, "list_fii_fundamentals", fake_list)

    with TestClient(app) as client:
        response = client.get("/api/v1/market/fundamentals/fii?ticker=hglg11")

    _clear_overrides()
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 100, "offset": 0}


def test_fundamentals_response_model_accepts_items():
    response = FiiFundamentalListResponse(items=[_fii()], total=1, limit=100, offset=0)
    assert response.items[0].ticker == "HGLG11"


def test_recommendation_endpoints_do_not_exist():
    with TestClient(app) as client:
        response = client.get("/api/v1/market/recommendations")
    assert response.status_code == 404
