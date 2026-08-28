from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.catalog import service
from backend.app.catalog.schemas import AssetCatalogCreate
from backend.app.core.database import get_session
from backend.app.main import app
from scripts.seed_catalog import collect_catalog_payloads, validate_csv_columns


def _stamp():
    return datetime(2026, 6, 1, tzinfo=timezone.utc)


def _asset(**overrides):
    base = {
        "id": 1,
        "ticker": "PETR4",
        "name": "Petrobras PN",
        "market": "acoes",
        "sector": "Petróleo e Gás",
        "segment": "Ações preferenciais",
        "currency": "BRL",
        "exchange": "B3",
        "source": "test",
        "is_active": True,
        "created_at": _stamp(),
        "updated_at": _stamp(),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


async def _fake_session():
    yield object()


async def _fake_user():
    return User(
        id=1,
        email="vinance@test.local",
        full_name="Vinance Test",
        hashed_password="not-used-in-test",
        is_active=True,
    )


def _install_overrides(authenticated=True):
    app.dependency_overrides[get_session] = _fake_session
    if authenticated:
        app.dependency_overrides[get_current_user] = _fake_user


def _clear_overrides():
    app.dependency_overrides.clear()


def test_ticker_is_normalized_uppercase():
    payload = AssetCatalogCreate(ticker=" petr4 ", name="Petrobras PN", market="acoes")
    assert payload.ticker == "PETR4"
    assert payload.normalized_payload()["currency"] == "BRL"


def test_invalid_market_is_rejected():
    with pytest.raises(ValueError):
        AssetCatalogCreate(ticker="PETR4", name="Petrobras PN", market="invalid")


def test_create_asset_endpoint(monkeypatch):
    _install_overrides()

    async def fake_create_asset(session, *, payload):
        return _asset(ticker=payload.ticker, market=payload.market, name=payload.name)

    monkeypatch.setattr(service, "create_asset", fake_create_asset)
    with TestClient(app) as client:
        response = client.post("/api/v1/catalog", json={"ticker": " petr4 ", "name": "Petrobras PN", "market": "acoes"})

    _clear_overrides()
    assert response.status_code == 201
    assert response.json()["ticker"] == "PETR4"


def test_list_catalog_with_market_filter(monkeypatch):
    _install_overrides(authenticated=False)

    async def fake_list_assets(session, *, market=None, is_active=True, search=None, limit=100, offset=0):
        assert market == "acoes"
        return [_asset()], 1

    monkeypatch.setattr(service, "list_assets", fake_list_assets)
    with TestClient(app) as client:
        response = client.get("/api/v1/catalog?market=acoes")

    _clear_overrides()
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["market"] == "acoes"


def test_get_asset_by_ticker_and_market(monkeypatch):
    _install_overrides(authenticated=False)

    async def fake_get(session, *, ticker, market, include_inactive=False):
        assert ticker == "petr4"
        assert market == "acoes"
        return _asset()

    monkeypatch.setattr(service, "get_asset_by_ticker_and_market", fake_get)
    with TestClient(app) as client:
        response = client.get("/api/v1/catalog/acoes/petr4")

    _clear_overrides()
    assert response.status_code == 200
    assert response.json()["ticker"] == "PETR4"


def test_update_asset_endpoint(monkeypatch):
    _install_overrides()

    async def fake_update(session, *, ticker, market, payload):
        return _asset(name=payload.name)

    monkeypatch.setattr(service, "update_asset", fake_update)
    with TestClient(app) as client:
        response = client.put("/api/v1/catalog/acoes/PETR4", json={"name": "Petrobras Atualizada"})

    _clear_overrides()
    assert response.status_code == 200
    assert response.json()["name"] == "Petrobras Atualizada"


def test_logical_delete_asset_endpoint(monkeypatch):
    _install_overrides()

    async def fake_deactivate(session, *, ticker, market):
        return _asset(is_active=False)

    monkeypatch.setattr(service, "deactivate_asset", fake_deactivate)
    with TestClient(app) as client:
        response = client.delete("/api/v1/catalog/acoes/PETR4")

    _clear_overrides()
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_seed_validates_required_columns(tmp_path):
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("ticker,name\nPETR4,Petrobras PN\n", encoding="utf-8")
    with pytest.raises(ValueError):
        validate_csv_columns(bad_csv)


def test_seed_avoids_duplicate_rows(tmp_path):
    csv_path = tmp_path / "acoes.csv"
    csv_path.write_text(
        "ticker,name,market,sector,segment,currency,exchange,source,is_active\n"
        "PETR4,Petrobras PN,acoes,Petróleo,Ação,BRL,B3,test,true\n"
        "petr4,Petrobras PN,acoes,Petróleo,Ação,BRL,B3,test,true\n",
        encoding="utf-8",
    )
    payloads, summary = collect_catalog_payloads(tmp_path)
    assert len(payloads) == 1
    assert payloads[0]["ticker"] == "PETR4"
    assert summary.ignored == 1
