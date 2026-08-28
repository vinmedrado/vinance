from __future__ import annotations

from backend.trading.config.settings import get_settings
from backend.trading.storage.database import create_sync_engine

from .config import BacktestingConfig
from .repository import BacktestingRepository
from .runner import BacktestRunner


def run_backtest(config: BacktestingConfig | None = None):
    config = config or BacktestingConfig()
    settings = get_settings()
    if settings.trading_mode != "PAPER_ONLY":
        raise RuntimeError("Backtesting V2 only runs in PAPER_ONLY mode.")
    engine = create_sync_engine(settings.database_url)
    try:
        repository = BacktestingRepository(engine, config)
        return BacktestRunner(repository, config).run()
    finally:
        engine.dispose()


def main() -> int:
    result = run_backtest()
    print(f"run_id={result.context.run_id}")
    print(f"period={result.context.start_time}..{result.context.end_time}")
    print(f"trades={result.metrics['number_of_trades']} final_capital={result.metrics['capital_final']:.6f}")
    print(
        f"candles_eligible={result.metrics['candles_eligible']} "
        f"warmup_skipped={result.metrics['warmup_candles_skipped']}"
    )
    print(
        f"inference_seconds={result.timings['inference_seconds']:.6f} "
        f"simulation_seconds={result.timings['simulation_seconds']:.6f} "
        f"total_seconds={result.timings['total_seconds']:.6f}"
    )
    print(f"reports={result.context.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
