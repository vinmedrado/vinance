"""
Shadow Mode Checkpoint — Vinance (versão para rodar DENTRO do container Docker)

Usa AsyncSessionLocal/asyncpg normalmente — dentro do container Linux não
existe o bug de asyncpg+Windows que travou a versão rodada direto no host.
DATABASE_URL vem do .env já carregado pelo container (aponta pro host
"postgres" da rede interna do Docker Compose, funciona sem configuração
extra).

COMO USAR (do Windows, na raiz do projeto):
    docker compose cp scripts\\shadow_mode_checkpoint.py backend:/app/scripts/shadow_mode_checkpoint.py
    docker compose exec backend python scripts/shadow_mode_checkpoint.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from backend.app.core.database import AsyncSessionLocal
from backend.app.intelligence.asset_score_model import AssetScore
from backend.app.intelligence.backtest.engine import (
    FeaturePoint,
    PricePoint,
    run_ranking_backtest,
)
from backend.app.market.models.acoes import AcaoFundamental
from backend.app.market.models.bdr import BdrFundamental
from backend.app.market.models.etf import EtfFundamental
from backend.app.market.models.fii import FiiFundamental

HOLDING_PERIOD_DAYS = 90
TOP_N = 5
REBALANCE_FREQUENCY = "monthly"

MARKET_MODEL = {
    "FII": FiiFundamental,
    "ACOES": AcaoFundamental,
    "ETF": EtfFundamental,
    "BDR": BdrFundamental,
}


async def _load_scores(session, market: str) -> list[FeaturePoint]:
    stmt = select(AssetScore.ticker, AssetScore.date, AssetScore.score_total).where(
        AssetScore.market == market
    )
    rows = (await session.execute(stmt)).all()
    return [FeaturePoint(ticker=r.ticker, date=r.date, score_final=r.score_total) for r in rows]


async def _load_prices(session, market: str) -> list[PricePoint]:
    model = MARKET_MODEL[market]
    stmt = select(model.ticker, model.date, model.price)
    rows = (await session.execute(stmt)).all()
    return [PricePoint(ticker=r.ticker, date=r.date, close=r.price) for r in rows]


def _readiness(features: list[FeaturePoint]) -> tuple[bool, str]:
    if not features:
        return False, "Nenhum AssetScore encontrado ainda para este mercado."
    oldest_signal = min(f.date for f in features)
    days_collected = (date.today() - oldest_signal).days
    missing = HOLDING_PERIOD_DAYS - days_collected
    if missing > 0:
        return (
            False,
            f"Faltam ~{missing} dias de coleta para fechar o primeiro ciclo "
            f"de {HOLDING_PERIOD_DAYS} dias (sinal mais antigo: {oldest_signal.isoformat()}, "
            f"{days_collected} dias coletados até hoje).",
        )
    return True, f"Dado suficiente para pelo menos 1 ciclo fechado ({days_collected} dias coletados)."


async def checkpoint_market(market: str) -> None:
    async with AsyncSessionLocal() as session:
        features = await _load_scores(session, market)
        ready, message = _readiness(features)
        print(f"\n=== {market} ===")
        print(message)
        if not ready:
            return

        prices = await _load_prices(session, market)
        start = min(f.date for f in features)
        end = date.today() - timedelta(days=1)

        result = run_ranking_backtest(
            market=market,
            features=features,
            prices=prices,
            start_date=start,
            end_date=end,
            holding_period_days=HOLDING_PERIOD_DAYS,
            top_n=TOP_N,
            rebalance_frequency=REBALANCE_FREQUENCY,
        )

        print(f"Amostra (trades fechados): {result['sample_size']}")
        for key, value in result["metrics"].items():
            print(f"  {key}: {value}")
        if result["sample_size"] < 10:
            print(
                "  AVISO: menos de 10 trades fechados. Amostra pequena demais "
                "para tirar qualquer conclusão sobre confiabilidade do score."
            )
        if result["warnings"]:
            print(f"  ({len(result['warnings'])} avisos internos, ex.: {result['warnings'][0]})")


async def main() -> None:
    for market in MARKET_MODEL:
        await checkpoint_market(market)


if __name__ == "__main__":
    asyncio.run(main())
