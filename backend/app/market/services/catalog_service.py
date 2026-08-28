from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.catalog.models import AssetCatalog
from backend.app.catalog.schemas import normalize_market


_MARKET_ALIASES = {
    "FII": "fii",
    "FIIS": "fii",
    "ACOES": "acoes",
    "AÇÕES": "acoes",
    "ACAO": "acoes",
    "AÇÃO": "acoes",
    "ETF": "etf",
    "ETFS": "etf",
    "BDR": "bdr",
    "BDRS": "bdr",
    "CRIPTO": "cripto",
    "CRYPTO": "cripto",
    "RENDA_FIXA": "renda_fixa",
    "RENDA FIXA": "renda_fixa",
}


def _normalize_market_alias(market: str) -> str:
    raw_market = str(market).strip()
    alias = _MARKET_ALIASES.get(raw_market.upper(), raw_market)
    return normalize_market(alias)


class CatalogService:
    """Read-only access to active tickers from asset_catalog for market jobs."""

    async def list_tickers(self, session: AsyncSession, market: str) -> list[str]:
        normalized_market = _normalize_market_alias(market)
        query = (
            select(AssetCatalog.ticker)
            .where(
                AssetCatalog.market == normalized_market,
                AssetCatalog.is_active.is_(True),
                AssetCatalog.ticker.is_not(None),
                func.trim(AssetCatalog.ticker) != "",
            )
            .order_by(AssetCatalog.ticker.asc())
        )
        result = await session.execute(query)
        return [str(ticker).strip().upper() for ticker in result.scalars().all() if str(ticker).strip()]

    async def count_by_market(self, session: AsyncSession) -> dict[str, int]:
        query = (
            select(AssetCatalog.market, func.count(AssetCatalog.id))
            .where(
                AssetCatalog.is_active.is_(True),
                AssetCatalog.ticker.is_not(None),
                func.trim(AssetCatalog.ticker) != "",
            )
            .group_by(AssetCatalog.market)
            .order_by(AssetCatalog.market.asc())
        )
        result = await session.execute(query)
        return {str(market): int(total) for market, total in result.all()}
