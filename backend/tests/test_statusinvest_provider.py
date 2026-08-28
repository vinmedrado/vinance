from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from backend.app.market.normalizers.statusinvest import merge_html_fallback, normalize_acoes, normalize_fiis
from backend.app.market.parsers.statusinvest_html import parse_acao_fallback, parse_fii_fallback
from backend.app.market.providers.statusinvest import StatusInvestClient
from backend.app.market.services.statusinvest_service import _apply_html_fallback, _chunks


def test_statusinvest_normalize_acoes_payload_mapping() -> None:
    payload = {
        "data": [
            {
                "ticker": "ABCD3",
                "companyName": "ABCD SA",
                "p_L": "10,5",
                "p_VP": 1.2,
                "p_SR": "2,1",
                "roe": "15,3",
                "roic": "11,0",
                "margemLiquida": "8,4",
                "dividaLiquidaEbitda": "1,7",
                "liquidezMediaDiaria": "1234567",
            }
        ]
    }
    rows = normalize_acoes(payload, allowed_tickers={"ABCD3"}, reference_date=date(2026, 1, 1))
    assert rows[0]["ticker"] == "ABCD3"
    assert rows[0]["pl"] == Decimal("10.5")
    assert rows[0]["pvp"] == Decimal("1.2")
    assert rows[0]["source"] == "statusinvest_json"


def test_statusinvest_normalize_fiis_payload_mapping() -> None:
    payload = {
        "data": [
            {
                "ticker": "XPTO11",
                "name": "XPTO FII",
                "p_VP": "0,93",
                "dy": "11,2",
                "liquidezMediaDiaria": "998877",
                "segmento": "Tijolo",
                "patrimonioLiquido": "1000000",
                "vpa": "95,7",
            }
        ]
    }
    rows = normalize_fiis(payload, allowed_tickers={"XPTO11"}, reference_date=date(2026, 1, 1))
    assert rows[0]["ticker"] == "XPTO11"
    assert rows[0]["pvp"] == Decimal("0.93")
    assert rows[0]["dy_12m"] == Decimal("11.2")
    assert rows[0]["liquidez_diaria"] == Decimal("998877")


def test_statusinvest_html_parser_fii_fallback_semantic_labels() -> None:
    html = """
    <html><body>
      <section><span>Vacância Física</span><strong>7,5%</strong></section>
      <section><span>Vacância Financeira</span><strong>3,2%</strong></section>
      <section><span>Gestora</span><strong>Gestora XPTO</strong></section>
      <section><span>Taxa de Administração</span><strong>0,95%</strong></section>
      <section><span>Nº de imóveis</span><strong>12</strong></section>
    </body></html>
    """
    parsed = parse_fii_fallback(html)
    assert parsed["vacancia_fisica"] == Decimal("7.5")
    assert parsed["vacancia_financeira"] == Decimal("3.2")
    assert parsed["gestora"] == "Gestora XPTO"
    assert parsed["taxa_adm"] == Decimal("0.95")
    assert parsed["num_imoveis"] == 12


def test_statusinvest_html_parser_acao_fallback_semantic_labels() -> None:
    html = """
    <html><body>
      <div><span>Margem Líquida</span><b>18,4%</b></div>
      <div><span>EV/EBITDA</span><b>7,1</b></div>
    </body></html>
    """
    parsed = parse_acao_fallback(html)
    assert parsed["margem_liquida"] == Decimal("18.4")
    assert parsed["ev_ebitda"] == Decimal("7.1")


def test_statusinvest_source_confidence_html_fallback() -> None:
    item = {"ticker": "XPTO11", "name": "XPTO", "date": date(2026, 1, 1), "source": "statusinvest_json", "vacancia_fisica": None}
    merged, confidence = merge_html_fallback(item, {"vacancia_fisica": Decimal("5.5")}, market="fii")
    assert confidence == "html_fallback"
    assert merged["source"] == "statusinvest_html_fallback"
    assert merged["vacancia_fisica"] == Decimal("5.5")


def test_statusinvest_batch_limit_chunks() -> None:
    items = list(range(601))
    chunks = list(_chunks(items, 300))
    assert len(chunks) == 3
    assert max(len(chunk) for chunk in chunks) == 300


@pytest.mark.asyncio
async def test_statusinvest_apply_html_fallback_uses_client_only_when_missing() -> None:
    client = StatusInvestClient()
    client.get_asset_page = AsyncMock(return_value="<span>Vacância Física</span><strong>4,2%</strong>")  # type: ignore[method-assign]
    item = {"ticker": "XPTO11", "name": "XPTO", "date": date(2026, 1, 1), "source": "statusinvest_json", "vacancia_fisica": None}
    final, confidence = await _apply_html_fallback(client=client, item=item, market="fii", enable_html_fallback=True)
    assert confidence == "html_fallback"
    assert final["vacancia_fisica"] == Decimal("4.2")


@pytest.mark.asyncio
async def test_statusinvest_provider_429_is_controlled(monkeypatch: pytest.MonkeyPatch) -> None:
    client = StatusInvestClient(min_interval_seconds=0, cooldown_429_seconds=0)

    async def fake_request(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("Status Invest rate limit reached")

    monkeypatch.setattr(client, "_request", fake_request)
    payload = await client.get_acoes_batch(["ABCD3"])
    assert payload["data"] == []
    assert "error" in payload
