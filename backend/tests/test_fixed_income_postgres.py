from __future__ import annotations

from datetime import date
from decimal import Decimal
import os

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.catalog.models import AssetCatalog
from backend.app.market.models import RendaFixaProduto
from backend.app.market.service import sync_renda_fixa_produtos


TEST_DATABASE_URL = os.getenv("AUTOPILOT_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="set AUTOPILOT_TEST_DATABASE_URL to an isolated PostgreSQL database",
)


def _product(source_product_id: str, *, name: str, rate: str) -> dict:
    return {
        "source_product_id": source_product_id,
        "nome": name,
        "emissor": "Tesouro Nacional",
        "tipo": "TREASURY_SELIC",
        "indexador": "SELIC",
        "rate_type": "FLOATING_SPREAD",
        "purchase_rate": Decimal(rate),
        "redemption_rate": Decimal(rate),
        "unit_price": Decimal("1000.00"),
        "redemption_unit_price": Decimal("999.00"),
        "base_unit_price": Decimal("999.50"),
        "vencimento": date(2032, 3, 1),
        "liquidity_type": "DAILY_REPURCHASE",
        "investimento_minimo": Decimal("10.00"),
        "garantia_fgc": False,
        "guarantee_type": "SOVEREIGN_ISSUER",
        "currency": "BRL",
        "market_date": date(2026, 10, 9),
        "source": "phase_d_fixed_income_test",
        "is_active": True,
    }


@pytest.mark.asyncio
async def test_real_postgres_snapshot_is_idempotent_and_deactivates_missing_rows() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    source = "phase_d_fixed_income_test"

    async def cleanup() -> None:
        async with sessions() as session:
            await session.execute(
                delete(RendaFixaProduto).where(RendaFixaProduto.source == source)
            )
            await session.execute(
                delete(AssetCatalog).where(AssetCatalog.source == source)
            )
            await session.commit()

    await cleanup()
    try:
        first_snapshot = [
            _product("tesouro-selic:2032-03-01", name="Tesouro Selic 2032", rate="0.05"),
            _product("tesouro-selic:2035-03-01", name="Tesouro Selic 2035", rate="0.06"),
            _product("tesouro-selic:2038-03-01", name="Tesouro Selic 2038", rate="0.07"),
            _product("tesouro-selic:2041-03-01", name="Tesouro Selic 2041", rate="0.08"),
        ]
        async with sessions() as session:
            first = await sync_renda_fixa_produtos(
                session, produtos=first_snapshot, source=source
            )
        assert first == {
            "processed": 4,
            "inserted": 4,
            "updated": 0,
            "deactivated": 0,
        }

        second_snapshot = [
            _product(
                "tesouro-selic:2032-03-01",
                name="Tesouro Selic 2032",
                rate="0.09",
            ),
            first_snapshot[1],
            first_snapshot[2],
        ]
        async with sessions() as session:
            second = await sync_renda_fixa_produtos(
                session, produtos=second_snapshot, source=source
            )
        assert second == {
            "processed": 3,
            "inserted": 0,
            "updated": 3,
            "deactivated": 1,
        }

        async with sessions() as session:
            rows = list(
                (
                    await session.execute(
                        select(RendaFixaProduto)
                        .where(RendaFixaProduto.source == source)
                        .order_by(RendaFixaProduto.source_product_id)
                    )
                )
                .scalars()
                .all()
            )
            catalogs = list(
                (
                    await session.execute(
                        select(AssetCatalog)
                        .where(AssetCatalog.source == source)
                        .order_by(AssetCatalog.ticker)
                    )
                )
                .scalars()
                .all()
            )

        assert len(rows) == 4
        assert rows[0].purchase_rate == Decimal("0.090000")
        assert rows[0].is_active is True
        assert rows[-1].is_active is False
        assert len({row.source_product_id for row in rows}) == 4
        assert len(catalogs) == 4
        assert sorted(item.is_active for item in catalogs) == [False, True, True, True]

        # A truncated but otherwise valid provider response cannot deactivate
        # most of the last-known-good universe.
        async with sessions() as session:
            with pytest.raises(ValueError, match="unexpectedly smaller"):
                await sync_renda_fixa_produtos(
                    session,
                    produtos=[second_snapshot[0]],
                    source=source,
                )

        async with sessions() as session:
            with pytest.raises(ValueError, match="duplicate source product identity"):
                await sync_renda_fixa_produtos(
                    session,
                    produtos=[second_snapshot[0], second_snapshot[0]],
                    source=source,
                )
    finally:
        await cleanup()
        await engine.dispose()


@pytest.mark.asyncio
async def test_real_postgres_sync_failure_rolls_back_the_whole_snapshot() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    source = "phase_d_fixed_income_rollback_test"

    async def cleanup() -> None:
        async with sessions() as session:
            await session.execute(
                delete(RendaFixaProduto).where(RendaFixaProduto.source == source)
            )
            await session.execute(
                delete(AssetCatalog).where(AssetCatalog.source == source)
            )
            await session.commit()

    await cleanup()
    try:
        original = _product(
            "tesouro-selic:2032-03-01",
            name="Tesouro Selic 2032",
            rate="0.05",
        )
        original["source"] = source
        async with sessions() as session:
            await sync_renda_fixa_produtos(
                session, produtos=[original], source=source
            )

        changed = {**original, "purchase_rate": Decimal("0.99")}
        conflicting = {
            **original,
            "source_product_id": "different-source-id-same-legacy-identity",
        }
        with pytest.raises(IntegrityError):
            async with sessions() as session:
                await sync_renda_fixa_produtos(
                    session,
                    produtos=[changed, conflicting],
                    source=source,
                )

        async with sessions() as session:
            rows = list(
                (
                    await session.execute(
                        select(RendaFixaProduto).where(
                            RendaFixaProduto.source == source
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert len(rows) == 1
        assert rows[0].purchase_rate == Decimal("0.050000")
    finally:
        await cleanup()
        await engine.dispose()
