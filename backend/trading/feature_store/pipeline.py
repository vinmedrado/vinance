from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy.engine import Engine

from backend.trading.config import get_settings
from backend.trading.storage.database import create_sync_engine

from .builder import FeatureBuilder
from .config import DEFAULT_CONFIG, FeatureStoreConfig
from .models import PipelineRunResult
from .repository import FeatureStoreRepository


class FeatureStorePipeline:
    def __init__(
        self,
        engine: Engine,
        config: FeatureStoreConfig = DEFAULT_CONFIG,
        builder: FeatureBuilder | None = None,
        repository: FeatureStoreRepository | None = None,
    ) -> None:
        self.engine = engine
        self.config = config
        self.builder = builder or FeatureBuilder(config=config)
        self.repository = repository or FeatureStoreRepository(engine, config=config)

    def run_symbol(
        self,
        symbol: str,
        interval: str,
        exchange: str = "binance",
        *,
        limit: int | None = None,
        ensure_schema: bool = True,
    ) -> PipelineRunResult:
        started_perf = time.perf_counter()
        started_at = datetime.now(timezone.utc)
        if ensure_schema:
            self.repository.ensure_schema()

        last_feature_time = self.repository.get_last_feature_time(
            symbol=symbol,
            interval=interval,
            exchange=exchange,
            feature_version=self.config.feature_version,
        )
        candles, truncated = self.repository.load_full_history_for_build(
            symbol=symbol,
            interval=interval,
            exchange=exchange,
            limit=limit,
        )
        build = self.builder.build(candles)
        persisted = self.repository.persist_features(
            build.frame,
            build.feature_columns,
            self.config.feature_version,
            only_after=last_feature_time,
        )
        elapsed = time.perf_counter() - started_perf
        finished_at = datetime.now(timezone.utc)
        null_counts = {
            column: int(build.frame[column].isna().sum())
            for column in build.feature_columns
            if column in build.frame.columns
        }
        latest_candle_time = None
        if not build.frame.empty:
            latest = build.frame["open_time"].iloc[-1]
            latest_candle_time = latest.to_pydatetime() if hasattr(latest, "to_pydatetime") else latest

        return PipelineRunResult(
            symbol=symbol,
            interval=interval,
            feature_version=self.config.feature_version,
            candles_loaded=int(len(candles)),
            rows_built=int(len(build.frame)),
            rows_persisted=persisted,
            feature_count=len(build.feature_columns),
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=elapsed,
            latest_candle_time=latest_candle_time,
            last_feature_time_before_run=last_feature_time,
            null_counts={
                **null_counts,
                "_history_truncated": int(truncated),
            },
        )


def run(
    symbol: str | None = None,
    interval: str | None = None,
    exchange: str | None = None,
    *,
    limit: int | None = None,
) -> list[PipelineRunResult]:
    settings = get_settings()
    engine = create_sync_engine(settings.database_url)
    pipeline = FeatureStorePipeline(engine)
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
        truncated = bool(result.null_counts.get("_history_truncated"))
        print(
            f"{result.symbol} {result.interval}: "
            f"candles={result.candles_loaded}, "
            f"features={result.feature_count}, "
            f"persisted={result.rows_persisted}, "
            f"elapsed={result.elapsed_seconds:.2f}s, "
            f"truncated={truncated}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
