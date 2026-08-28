from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.intelligence.allocation import calculate_allocation
from backend.app.intelligence.asset_scoring import SCORERS, rank_assets, score_asset
from backend.app.intelligence import service
from backend.app.main import app


async def _fake_session():
    yield object()


async def _fake_user():
    return User(id=7, email="vinance@test.local", full_name="Vinance Test", hashed_password="x", is_active=True)


def _install_auth_overrides():
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_session] = _fake_session


def _clear_overrides():
    app.dependency_overrides.clear()


def _sum_pct(result: dict) -> Decimal:
    return sum(item["percentage"] for item in result["allocation"])


def _pct(result: dict, asset_class: str) -> Decimal:
    return next(item["percentage"] for item in result["allocation"] if item["asset_class"] == asset_class)


def test_allocation_conservative_fecha_100():
    result = calculate_allocation(investment_capacity=1000, risk_profile="conservative", financial_score=80)
    assert _sum_pct(result) == Decimal("100.00")


def test_allocation_moderate_fecha_100():
    result = calculate_allocation(investment_capacity=1000, risk_profile="moderate", financial_score=80)
    assert _sum_pct(result) == Decimal("100.00")


def test_allocation_aggressive_fecha_100():
    result = calculate_allocation(investment_capacity=1000, risk_profile="aggressive", financial_score=80)
    assert _sum_pct(result) == Decimal("100.00")


def test_score_menor_40_zera_cripto():
    result = calculate_allocation(investment_capacity=1000, risk_profile="aggressive", financial_score=30)
    assert _pct(result, "cripto") == Decimal("0.00")
    assert result["adjusted_risk_profile"] == "conservative"


def test_emergency_reserve_priority_aumenta_renda_fixa():
    normal = calculate_allocation(investment_capacity=1000, risk_profile="moderate", financial_score=80, emergency_reserve_priority=False)
    adjusted = calculate_allocation(investment_capacity=1000, risk_profile="moderate", financial_score=80, emergency_reserve_priority=True)
    assert _pct(adjusted, "renda_fixa") > _pct(normal, "renda_fixa")


def test_high_risk_allowed_false_bloqueia_cripto():
    result = calculate_allocation(investment_capacity=1000, risk_profile="moderate", financial_score=80, high_risk_allowed=False)
    assert _pct(result, "cripto") == Decimal("0.00")


def test_asset_scoring_nao_quebra_com_dados_ausentes():
    for asset_class in SCORERS:
        scored = score_asset({}, asset_class)
        assert scored["score"] == 50
        assert scored["missing_fields"]


def test_score_sempre_entre_0_e_100():
    assets = {
        "fii": {"ticker": "HGLG11", "dy_12m": 500, "pvp": -2, "vacancia_fisica": 999, "liquidez_diaria": 999999999},
        "acoes": {"ticker": "PETR4", "roe": 500, "pl": -1, "dy_12m": 40, "divida_liq_ebitda": 999, "volume_medio_diario": 999999999},
        "etf": {"ticker": "BOVA11", "taxa_adm": 9, "tracking_error": 9, "retorno_12m": 80, "volume_medio_diario": 999999999},
        "bdr": {"ticker": "AAPL34", "dy_12m": 30, "volume_medio_diario_brl": 999999999, "cotacao_cambio": 20},
        "cripto": {"ticker": "BTC", "market_cap_rank": 999, "volume_24h_usd": 9999999999, "price_change_30d_pct": 300, "ath_change_pct": 80},
        "renda_fixa": {"nome": "CDB", "taxa_total_equiv": 200, "liquidez_dias": 2000, "garantia_fgc": True, "vencimento": date(2030, 1, 1)},
    }
    for asset_class, payload in assets.items():
        scored = score_asset(payload, asset_class)
        assert 0 <= scored["score"] <= 100


def test_rank_assets_by_class_ordera_por_score():
    ranked = rank_assets("fii", [{"ticker": "A", "dy_12m": 2}, {"ticker": "B", "dy_12m": 12, "pvp": 0.8, "vacancia_fisica": 0, "liquidez_diaria": 2000000}])
    assert ranked[0]["ticker"] == "B"


def test_endpoint_exige_auth():
    _clear_overrides()
    with TestClient(app) as client:
        response = client.get("/api/v1/intelligence/recommendations")
    assert response.status_code == 401


def test_endpoint_retorna_allocation_mesmo_sem_fundamentos(monkeypatch):
    _install_auth_overrides()

    async def fake_context(session, *, user_id):
        return {
            "financial_score": 82,
            "investment_capacity": Decimal("1000.00"),
            "risk_profile": "moderate",
            "emergency_reserve_priority": False,
            "high_risk_allowed": True,
            "has_debt_default": False,
            "emergency_reserve_months": Decimal("6"),
            "monthly_salary": Decimal("5000"),
        }

    async def fake_assets(session):
        return {asset_class: [] for asset_class in service.ASSET_CLASSES}

    monkeypatch.setattr(service, "get_financial_context", fake_context)
    monkeypatch.setattr(service, "_read_assets_by_class", fake_assets)

    with TestClient(app) as client:
        response = client.get("/api/v1/intelligence/recommendations")

    _clear_overrides()
    assert response.status_code == 200
    payload = response.json()
    assert sum(Decimal(str(item["percentage"])) for item in payload["allocation"]) == Decimal("100.00")
    assert "dados de fundamentos ainda não disponíveis" in payload["warnings"]
    assert all(item["assets"] == [] for item in payload["recommendations_by_class"])


def test_nao_existe_chamada_externa_no_modulo_intelligence():
    import pathlib

    text = "\n".join(path.read_text() for path in pathlib.Path("backend/app/intelligence").glob("*.py"))
    forbidden = ["requests.", "httpx.", "aiohttp", "yfinance", "Groq", "groq", "Prophet", "LSTM"]
    assert not any(token in text for token in forbidden)
