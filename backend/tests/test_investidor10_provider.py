import pytest

from backend.app.market.providers.investidor10 import Investidor10Provider


def test_importa_investidor10_provider():
    provider = Investidor10Provider(delay_min=0, delay_max=0, retries=1, timeout=1)
    assert isinstance(provider, Investidor10Provider)


def test_br_number_to_float_converte_numero_br():
    assert Investidor10Provider.br_number_to_float("1.234,56") == 1234.56


def test_br_money_to_float_converte_bilhoes():
    assert Investidor10Provider.br_money_to_float("1,5 Bilhões") == 1_500_000_000


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("HTTP 404", "404_NAO_ENCONTRADO"),
        ("HTTP 410", "410_REMOVIDO"),
        ("HTTP 429", "429_RATE_LIMIT"),
        ("request timeout", "TIMEOUT"),
        ("Bloqueado por proteção do site", "BLOQUEIO"),
    ],
)
def test_classify_error_identifica_categorias(message, expected):
    assert Investidor10Provider.classify_error(message) == expected


def test_scrape_many_vazio_retorna_estrutura_sem_erro():
    provider = Investidor10Provider(delay_min=0, delay_max=0, retries=1, timeout=1)

    result = provider.scrape_many("FIIS", [])

    assert result["mercado"] == "FIIS"
    assert result["ativos"] == 0
    assert result["ok"] == 0
    assert result["erros"] == 0
    assert result["sucesso_pct"] == 0.0
    assert result["tempo_segundos"] == 0.0
    assert result["ativos_por_min"] == 0.0
    assert result["results"] == []
    assert result["errors"] == []


def test_scrape_many_mercado_invalido_levanta_value_error():
    provider = Investidor10Provider(delay_min=0, delay_max=0, retries=1, timeout=1)

    with pytest.raises(ValueError):
        provider.scrape_many("INVALIDO", [])
