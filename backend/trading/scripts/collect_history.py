from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone

from ..config import get_settings
from ..market_data.binance_public import BinancePublicProvider
from ..storage.database import create_sync_engine
from ..storage.repositories import CandleRepository

INTERVAL_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
}

DEFAULT_DAYS = 90
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]


def collect_symbol(provider, repository, symbol: str, interval: str, start: datetime, end: datetime) -> int:
    if interval not in INTERVAL_MS:
        raise ValueError(f"Intervalo não suportado: {interval}")

    cursor = start
    total = 0
    step = timedelta(milliseconds=INTERVAL_MS[interval])

    while cursor < end:
        frame = provider.fetch_candles(
            symbol=symbol,
            interval=interval,
            start=cursor,
            end=end,
            limit=1000,
        )
        if frame.empty:
            break

        total += repository.upsert_dataframe(frame)
        last_open = frame["open_time"].max().to_pydatetime()
        next_cursor = last_open + step
        if next_cursor <= cursor:
            raise RuntimeError(f"Cursor não avançou para {symbol}.")
        cursor = next_cursor
        print(f"{symbol}: {total} candles processados até {last_open.isoformat()}")
        time.sleep(0.15)

        if len(frame) < 1000:
            break

    return total


def main() -> int:
    settings = get_settings()
    if settings.trading_mode != "PAPER_ONLY":
        print("Execução bloqueada: use TRADING_MODE=PAPER_ONLY.", file=sys.stderr)
        return 1

    symbols = settings.trading_symbols or DEFAULT_SYMBOLS
    interval = settings.trading_interval
    days = int(getattr(settings, "trading_history_days", DEFAULT_DAYS) or DEFAULT_DAYS)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    engine = create_sync_engine(settings.database_url)
    provider = BinancePublicProvider()
    repository = CandleRepository(engine)

    print("=" * 72)
    print("VINANCE — COLETA HISTÓRICA BINANCE")
    print("=" * 72)
    print(f"Ativos: {symbols}")
    print(f"Intervalo: {interval}")
    print(f"Período: {start.isoformat()} até {end.isoformat()}")

    failures = 0
    try:
        for symbol in symbols:
            try:
                total = collect_symbol(provider, repository, symbol, interval, start, end)
                print(f"{symbol}: concluído com {total} candles processados.\n")
            except Exception as error:
                failures += 1
                print(f"{symbol}: ERRO — {error}", file=sys.stderr)
        return 0 if failures == 0 else 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
