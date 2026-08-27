import pytest

from backend.app.market.services.investidor10_sync import Investidor10SyncService


class FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False
        self.rolled_back = False

    def add(self, obj):
        self.added.append(obj)

    async def execute(self, stmt):
        return FakeScalarResult()

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


class FakeProvider:
    def _scrape_by_market(self, mercado, ticker):
        return {
            "ticker": ticker,
            "name": ticker,
            "data_processado": "2026-06-09",
            "valor_atual_num": 160.25,
        }

    def scrape_many(self, mercado, tickers, workers=None):
        return {
            "mercado": mercado,
            "ativos": len(tickers),
            "ok": len(tickers),
            "erros": 0,
            "sucesso_pct": 100.0,
            "tempo_segundos": 0.01,
            "results": [],
            "errors": [],
        }


class FakeScalarResult:
    def scalar_one_or_none(self):
        return None


def test_import_service():
    assert Investidor10SyncService is not None


def test_invalid_market_raises_value_error():
    service = Investidor10SyncService(provider=FakeProvider())
    with pytest.raises(ValueError):
        service._normalize_market("INVALIDO")


def test_map_fiis_payload():
    service = Investidor10SyncService(provider=FakeProvider())
    mapped = service._map_payload("FIIS", {
        "ticker": "hglg11",
        "name": "HGLG11",
        "data_processado": "2026-06-09",
        "valor_atual_num": 160.25,
        "patrimonio_num": 3_000_000_000,
        "p_vp_num": 1.02,
        "dividend_yield_num": 0.85,
        "numero_cotistas_num": 123456,
        "taxa_administracao_num": 0.9,
        "liquidez_diaria_num": 1000000,
        "segmento": "Logística",
        "tipo_gestao": "Ativa",
        "vacancia_num": 2.5,
        "dividendos_12m_num": 12.0,
    })
    assert mapped["ticker"] == "HGLG11"
    assert str(mapped["price"]) == "160.25"
    assert str(mapped["patrimonio_liq"]) == "3000000000"
    assert str(mapped["pvp"]) == "1.02"
    assert str(mapped["dy_12m"]) == "0.85"
    assert mapped["num_cotistas"] == 123456
    assert str(mapped["taxa_adm"]) == "0.9"
    assert str(mapped["liquidez_diaria"]) == "1000000"
    assert mapped["segmento"] == "Logística"
    assert mapped["tipo"] == "Ativa"
    assert str(mapped["vacancia_fisica"]) == "2.5"
    assert "dividendos_12m" not in mapped


def test_map_acoes_payload():
    service = Investidor10SyncService(provider=FakeProvider())
    mapped = service._map_payload("ACOES", {
        "ticker": "petr4",
        "data_processado": "2026-06-09",
        "valor_atual_num": 37.15,
        "valor_mercado_num": 500_000_000_000,
        "p_l_num": 5.5,
        "roe_num": 22.1,
        "dividend_yield_num": 10.2,
        "p_vp_num": 1.1,
        "psr_num": 1.7,
        "ev_ebitda_num": 4.2,
        "roic_num": 18.3,
        "margem_liquida_num": 20.5,
        "cagr_receita_5a_num": 8.4,
        "cagr_lucro_5a_num": 9.1,
        "divida_liquida_ebitda_num": 0.8,
        "liquidez_media_diaria_num": 250000000,
        "setor": "Petróleo",
        "subsetor": "Exploração",
        "segmento": "Campo inexistente no model",
    })
    assert mapped["ticker"] == "PETR4"
    assert str(mapped["price"]) == "37.15"
    assert str(mapped["market_cap"]) == "500000000000"
    assert str(mapped["pl"]) == "5.5"
    assert str(mapped["roe"]) == "22.1"
    assert str(mapped["dy_12m"]) == "10.2"
    assert str(mapped["pvp"]) == "1.1"
    assert str(mapped["psr"]) == "1.7"
    assert str(mapped["ev_ebitda"]) == "4.2"
    assert str(mapped["roic"]) == "18.3"
    assert str(mapped["margem_liquida"]) == "20.5"
    assert str(mapped["cagr_receita_5a"]) == "8.4"
    assert str(mapped["cagr_lucro_5a"]) == "9.1"
    assert str(mapped["divida_liq_ebitda"]) == "0.8"
    assert str(mapped["volume_medio_diario"]) == "250000000"
    assert mapped["setor"] == "Petróleo"
    assert mapped["subsetor"] == "Exploração"
    assert "segmento" not in mapped


def test_map_etf_payload():
    service = Investidor10SyncService(provider=FakeProvider())
    mapped = service._map_payload("ETF", {
        "ticker": "bova11",
        "data_processado": "2026-06-09",
        "valor_atual_num": 125.5,
        "taxa_num": 0.3,
        "rentabilidade_1a_num": 12.7,
        "rentabilidade_2a_num": 20.2,
        "variacao_12m_num": 9.4,
        "patrimonio_num": 12_000_000_000,
        "indice_referencia": "Ibovespa",
        "tipo": "Renda Variável",
        "liquidez_media_diaria_num": 150000000,
    })
    assert mapped["ticker"] == "BOVA11"
    assert str(mapped["price"]) == "125.5"
    assert str(mapped["taxa_adm"]) == "0.3"
    assert "rentabilidade_1a" not in mapped
    assert str(mapped["retorno_12m"]) == "9.4"
    assert str(mapped["retorno_24m"]) == "20.2"
    assert str(mapped["patrimonio_liq"]) == "12000000000"
    assert mapped["indice_replicado"] == "Ibovespa"
    assert mapped["tipo"] == "Renda Variável"
    assert str(mapped["volume_medio_diario"]) == "150000000"


def test_map_bdr_payload():
    service = Investidor10SyncService(provider=FakeProvider())
    mapped = service._map_payload("BDR", {
        "ticker": "aapl34",
        "data_processado": "2026-06-09",
        "preco_atual_num": 55.7,
        "p_l_num": 30.1,
        "p_vpa_num": 8.2,
        "score_num": 71.0,
        "liquidez_media_diaria_num": 1000000,
        "valor_mercado_num": 3_000_000_000_000,
        "dividend_yield_num": 0.6,
        "pais_origem": "Estados Unidos",
        "moeda": "USD",
    })
    assert mapped["ticker"] == "AAPL34"
    assert str(mapped["price"]) == "55.7"
    assert str(mapped["pl"]) == "30.1"
    assert str(mapped["pvp"]) == "8.2"
    assert "score" not in mapped
    assert str(mapped["volume_medio_diario_brl"]) == "1000000"
    assert str(mapped["market_cap"]) == "3000000000000"
    assert str(mapped["dy_12m"]) == "0.6"
    assert mapped["pais_origem"] == "Estados Unidos"
    assert mapped["moeda_origem"] == "USD"


def test_filter_model_fields_does_not_break_with_missing_field():
    class Columns:
        def keys(self):
            return ["ticker", "date", "source", "price"]

    class Table:
        columns = Columns()

    class DummyModel:
        __name__ = "DummyModel"
        __table__ = Table()

    service = Investidor10SyncService(provider=FakeProvider())
    filtered = service._filter_model_fields(DummyModel, {"ticker": "PETR4", "price": 10, "campo_inexistente": 1})
    assert filtered == {"ticker": "PETR4", "price": 10}


@pytest.mark.asyncio
async def test_sync_market_with_mocked_provider_returns_summary():
    service = Investidor10SyncService(provider=FakeProvider())
    session = FakeSession()
    result = await service.sync_market(session, "FIIS", ["HGLG11"], workers=1)
    assert result["source"] == "INVESTIDOR10"
    assert result["mercado"] == "FIIS"
    assert result["status"] == "SUCCESS"
    assert result["total"] == 1
    assert result["ok"] == 1
    assert session.committed is True
