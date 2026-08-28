from __future__ import annotations

from ..candles.validator import validate_candles
from ..config import get_settings
from ..market_data.binance_public import BinancePublicProvider
from ..storage.database import create_sync_engine
from ..storage.repositories import CandleRepository


def main() -> None:
    settings = get_settings()
    provider = BinancePublicProvider()
    repository = CandleRepository(create_sync_engine(settings.database_url))
    for symbol in settings.trading_symbols:
        candles = provider.fetch_candles(symbol, settings.trading_interval, limit=1000)
        errors = validate_candles(candles)
        if errors:
            print(f"{symbol}: falha de validação: {errors}")
            continue
        inserted = repository.upsert_dataframe(candles)
        print(f"{symbol}: {inserted} candles processados.")


if __name__ == "__main__":
    main()
