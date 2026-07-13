from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy.engine import Engine

from backend.trading.config import get_settings
from backend.trading.storage.database import create_sync_engine

from .builder import TargetBuilder
from .config import DEFAULT_CONFIG, TargetEngineConfig
from .models import TargetPipelineResult
from .repository import TargetRepository


class TargetEnginePipeline:
    def __init__(
        self,
        engine: Engine,
        config: TargetEngineConfig = DEFAULT_CONFIG,
        builder: TargetBuilder | None = None,
        repository: TargetRepository | None = None,
    ) -> None:
        self.engine = engine
        self.config = config
        self.builder = builder or TargetBuilder(config=config)
        self.repository = repository or TargetRepository(engine, config=config)

    def run_symbol(
        self,
        symbol: str,
        interval: str,
        exchange: str = "binance",
        *,
        limit: int | None = None,
        ensure_schema: bool = True,
    ) -> TargetPipelineResult:
        started_perf = time.perf_counter()
        started_at = datetime.now(timezone.utc)
        if ensure_schema:
            self.repository.ensure_schema()

        last_target_time = self.repository.get_last_target_time(
            symbol=symbol,
            interval=interval,
            exchange=exchange,
            specs=self.config.specs,
        )
        candles, truncated = self.repository.load_full_history_for_build(
            symbol=symbol,
            interval=interval,
            exchange=exchange,
            limit=limit,
        )
        build = self.builder.build(candles)
        persisted = self.repository.persist_targets(
            build.frame,
            build.specs,
            only_after=last_target_time,
        )
        elapsed = time.perf_counter() - started_perf
        finished_at = datetime.now(timezone.utc)
        latest_candle_time = None
        if not build.frame.empty:
            latest = build.frame["open_time"].iloc[-1]
            latest_candle_time = latest.to_pydatetime() if hasattr(latest, "to_pydatetime") else latest

        return TargetPipelineResult(
            symbol=symbol,
            interval=interval,
            target_version=self.config.target_version,
            candles_loaded=int(len(candles)),
            rows_built=int(len(build.frame)),
            targets_persisted=persisted,
            target_names=tuple(spec.name for spec in build.specs),
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=elapsed,
            latest_candle_time=latest_candle_time,
            last_target_time_before_run=last_target_time,
            metadata={"history_truncated": int(truncated), "spec_count": len(build.specs)},
        )


def run(
    symbol: str | None = None,
    interval: str | None = None,
    exchange: str | None = None,
    *,
    limit: int | None = None,
) -> list[TargetPipelineResult]:
    settings = get_settings()
    engine = create_sync_engine(settings.database_url)
    pipeline = TargetEnginePipeline(engine)
    symbols = [symbol.upper()] if symbol else settings.trading_symbols
    effective_interval = interval or settings.trading_interval
    effective_exchange = exchange or settings.trading_exchange
    try:
        return [
            pipeline.run_symbol(
                symbol=item,
                interval=effective_interval,
                exchange=effective_exchange,
                limit=limit,
            )
            for item in symbols
        ]
    finally:
        engine.dispose()


def main() -> int:
    results = run()
    for result in results:
        print(
            f"{result.symbol} {result.interval}: "
            f"candles={result.candles_loaded}, "
            f"target_specs={len(result.target_names)}, "
            f"persisted={result.targets_persisted}, "
            f"elapsed={result.elapsed_seconds:.2f}s, "
            f"truncated={bool(result.metadata.get('history_truncated'))}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
