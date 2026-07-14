from __future__ import annotations

from backend.trading.config import get_settings
from backend.trading.prediction_engine.pipeline import run_latest_prediction
from backend.trading.prediction_engine.models import PredictionResult
from backend.trading.storage.database import create_sync_engine

from .config import DEFAULT_CONFIG, PaperTradingConfig
from .executor import PaperTradingExecutor, parse_target_name
from .models import ExecutionResult, PortfolioState
from .portfolio import PortfolioManager
from .repository import PaperTradingRepository
from .reports import PaperTradingReportWriter


class PaperTradingPipeline:
    def __init__(
        self,
        repository: PaperTradingRepository,
        config: PaperTradingConfig = DEFAULT_CONFIG,
        executor: PaperTradingExecutor | None = None,
        portfolio: PortfolioState | None = None,
        report_writer: PaperTradingReportWriter | None = None,
    ) -> None:
        self.repository = repository
        self.config = config
        self.executor = executor or PaperTradingExecutor(config)
        self.portfolio = portfolio or PortfolioManager(config).initial_state()
        self.report_writer = report_writer or PaperTradingReportWriter(config)

    def run_prediction(self, prediction: PredictionResult, *, candle_index: int = 0) -> ExecutionResult:
        target_rules = parse_target_name(prediction.target_name)
        entry_candle = self.repository.load_entry_candle(
            candle_id=prediction.candle_id,
            symbol=prediction.symbol,
            interval=prediction.interval,
        )
        future_candles = self.repository.load_future_candles(
            symbol=prediction.symbol,
            interval=prediction.interval,
            after_open_time=entry_candle.open_time,
            limit=target_rules.horizon_candles,
        )
        result = self.executor.execute(
            prediction=prediction,
            entry_candle=entry_candle,
            future_candles=future_candles,
            portfolio=self.portfolio,
            candle_index=candle_index,
        )
        reports = self.report_writer.write_all(self.portfolio)
        return ExecutionResult(result.opened_position, result.closed_trade, self.portfolio, result.reason, reports)


def run_latest_paper_simulation() -> ExecutionResult:
    settings = get_settings()
    if settings.trading_mode != "PAPER_ONLY":
        raise RuntimeError("Paper Trading V2 only runs in PAPER_ONLY mode.")
    prediction = run_latest_prediction()
    engine = create_sync_engine(settings.database_url)
    try:
        pipeline = PaperTradingPipeline(PaperTradingRepository(engine))
        return pipeline.run_prediction(prediction)
    finally:
        engine.dispose()


def main() -> int:
    result = run_latest_paper_simulation()
    print(f"reason={result.reason}")
    if result.opened_position:
        print(
            f"opened position={result.opened_position.position_id} "
            f"entry={result.opened_position.entry_price:.6f} "
            f"qty={result.opened_position.quantity:.8f}"
        )
    if result.closed_trade:
        print(
            f"closed reason={result.closed_trade.exit_reason} "
            f"pnl={result.closed_trade.net_pnl:.6f} "
            f"exit={result.closed_trade.exit_price:.6f}"
        )
    print(f"equity={result.portfolio.equity:.6f} drawdown={result.portfolio.max_drawdown:.6f}")
    print(f"reports={result.reports}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
