from __future__ import annotations

from backend.trading.config import get_settings
from backend.trading.storage.database import create_sync_engine

from .config import DEFAULT_CONFIG, PredictionEngineConfig
from .loader import PredictionArtifactLoader
from .models import PredictionResult
from .predictor import PredictionPredictor
from .repository import PredictionRepository
from .reports import PredictionReportWriter


class PredictionEngine:
    def __init__(
        self,
        repository: PredictionRepository,
        config: PredictionEngineConfig = DEFAULT_CONFIG,
        loader: PredictionArtifactLoader | None = None,
        predictor: PredictionPredictor | None = None,
        report_writer: PredictionReportWriter | None = None,
    ) -> None:
        self.repository = repository
        self.config = config
        self.loader = loader or PredictionArtifactLoader(config)
        self.predictor = predictor or PredictionPredictor(config)
        self.report_writer = report_writer or PredictionReportWriter(config)

    def predict_latest(
        self,
        *,
        symbol: str,
        interval: str,
        target_name: str,
    ) -> PredictionResult:
        self._assert_paper_only()
        entry = self.loader.select_best_model(symbol=symbol, interval=interval, target_name=target_name)
        artifacts = self.loader.load_artifacts(entry)
        prediction_input = self.repository.load_latest_features(symbol=symbol, interval=interval)
        result = self.predictor.predict(prediction_input, artifacts)
        return self.report_writer.write(result)

    def _assert_paper_only(self) -> None:
        settings = get_settings()
        if settings.trading_mode != "PAPER_ONLY" or not self.config.paper_only:
            raise RuntimeError("Prediction Engine V2 only runs in PAPER_ONLY mode.")


def run_latest_prediction() -> PredictionResult:
    settings = get_settings()
    engine = create_sync_engine(settings.database_url)
    try:
        repository = PredictionRepository(engine)
        prediction_engine = PredictionEngine(repository)
        return prediction_engine.predict_latest(
            symbol="BTCUSDT",
            interval=settings.trading_interval,
            target_name="v2_long_tp_100bps_sl_50bps_h_24",
        )
    finally:
        engine.dispose()


def main() -> int:
    result = run_latest_prediction()
    print(f"{result.symbol} {result.interval} {result.target_name}")
    print(
        f"class={result.predicted_class} "
        f"p_sl={result.probability_stop_loss:.6f} "
        f"p_neutral={result.probability_neutral:.6f} "
        f"p_tp={result.probability_take_profit:.6f} "
        f"decision={result.decision} "
        f"confidence={result.confidence:.6f} "
        f"confidence_level={result.confidence_level}"
    )
    print(f"model={result.model_name} candle_id={result.candle_id} prediction_id={result.prediction_id} report={result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
