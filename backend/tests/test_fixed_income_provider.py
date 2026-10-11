from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from backend.app.market.providers.tesouro import (
    TesouroDiretoProvider,
    TesouroProviderError,
)


HEADER = (
    "Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;"
    "Taxa Venda Manha;PU Compra Manha;PU Venda Manha;PU Base Manha\n"
)


def test_provider_selects_latest_official_market_date_and_uses_decimal() -> None:
    content = HEADER + (
        "Tesouro Selic;01/03/2029;08/10/2026;0,04;0,05;20000,00;19990,00;19995,00\n"
        "Tesouro Selic;01/03/2029;09/10/2026;0,05;0,06;20046,46;20031,46;20031,46\n"
        "Tesouro IPCA+;15/05/2045;09/10/2026;6,80;6,92;4500,12;4480,10;4490,00\n"
    )

    rows = TesouroDiretoProvider().parse_csv(
        content,
        observed_at=datetime(2026, 10, 10, tzinfo=timezone.utc),
    )

    assert len(rows) == 2
    selic = next(item for item in rows if item["tipo"] == "TREASURY_SELIC")
    assert selic["source_product_id"] == "tesouro-selic:2029-03-01"
    assert selic["market_date"] == date(2026, 10, 9)
    assert selic["unit_price"] == Decimal("20046.46")
    assert selic["investimento_minimo"] == Decimal("200.47")
    assert selic["liquidez_dias"] is None
    assert selic["liquidity_type"] == "DAILY_REPURCHASE"
    assert selic["garantia_fgc"] is False
    assert selic["guarantee_type"] == "SOVEREIGN_ISSUER"


def test_provider_identity_is_not_the_display_name() -> None:
    content = HEADER + (
        "Tesouro Prefixado;01/01/2032;09/10/2026;12,10;12,20;700,00;695,00;697,00\n"
    )
    provider = TesouroDiretoProvider()

    first = provider.parse_csv(
        content,
        observed_at=datetime(2026, 10, 10, tzinfo=timezone.utc),
    )[0]
    second = provider.parse_csv(
        content.replace("Tesouro Prefixado", "Tesouro  Prefixado"),
        observed_at=datetime(2026, 10, 10, tzinfo=timezone.utc),
    )[0]

    assert first["source_product_id"] == second["source_product_id"]
    assert first["source_product_id"] != first["nome"]


def test_provider_rejects_unrecognized_or_empty_contract() -> None:
    provider = TesouroDiretoProvider()
    with pytest.raises(TesouroProviderError):
        provider.parse_csv(
            "wrong;header\nvalue;value\n",
            observed_at=datetime(2026, 10, 10, tzinfo=timezone.utc),
        )


def test_latest_snapshot_with_invalid_identity_fails_closed() -> None:
    provider = TesouroDiretoProvider()
    content = HEADER + (
        "Tesouro Selic;;09/10/2026;0,05;0,06;"
        "10000,00;9990,00;9995,00\n"
    )

    with pytest.raises(TesouroProviderError):
        provider.parse_csv(
            content,
            observed_at=datetime(2026, 10, 10, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio
async def test_provider_failure_is_not_reinterpreted_as_empty(monkeypatch) -> None:
    class FailedResponse:
        def raise_for_status(self):
            raise RuntimeError("provider unavailable")

    class FailedClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            return FailedResponse()

    monkeypatch.setattr(
        "backend.app.market.providers.tesouro.httpx.AsyncClient",
        lambda **kwargs: FailedClient(),
    )

    with pytest.raises(TesouroProviderError):
        await TesouroDiretoProvider(retries=0).fetch_produtos()
