from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.trading.config import get_settings
from backend.trading.storage.database import create_sync_engine

from .calibration import calibrate_if_applicable
from .config import DEFAULT_CONFIG, MLEngineConfig
from .dataset import temporal_split, walk_forward_splits
from .evaluator import evaluate_model
from .models import TrainedModel, TrainingReport
from .registry import model_registry
from .reports import compact_model_report, update_manifest
from .repository import MLEngineRepository
from .serialization import model_artifact_dir, save_artifacts
from .trainer import fit_preprocessing, select_best_model, train_estimator, validate_training_data


class MLEnginePipeline:
    def __init__(self, repository: MLEngineRepository, config: MLEngineConfig = DEFAULT_CONFIG) -> None:
        self.repository = repository
        self.config = config

    def train_target(
        self,
        *,
        symbol: str,
        interval: str,
        target_name: str,
        limit: int | None = None,
        models: tuple[str, ...] | None = None,
    ) -> TrainingReport:
        dataset = self.repository.load_dataset(symbol=symbol, interval=interval, target_name=target_name, limit=limit)
        if dataset.sample_count < self.config.min_samples:
            raise ValueError(f"Dataset has {dataset.sample_count} samples; minimum is {self.config.min_samples}.")
        split = temporal_split(dataset, self.config.split)
        validate_training_data(split.train, min_class_count=self.config.min_class_count)

        registry = model_registry(self.config)
        selected_names = models or tuple(registry.keys())
        trained: dict[str, TrainedModel] = {}
        for model_name in selected_names:
            if model_name not in registry:
                continue
            preprocessing = fit_preprocessing(split.train, dataset.feature_columns)
            estimator = registry[model_name]()
            estimator = train_estimator(estimator, preprocessing, split.train)
            validation = evaluate_model(
                model_name=model_name,
                estimator=estimator,
                preprocessing=preprocessing,
                frame=split.validation,
                config=self.config,
            )
            trained[model_name] = TrainedModel(
                model_name=model_name,
                estimator=estimator,
                preprocessing=preprocessing,
                validation=validation,
            )

        best_name = select_best_model(trained, self.config.best_metric)
        best = trained[best_name]
        calibrated_estimator, calibrated = calibrate_if_applicable(best.estimator, best.preprocessing, split.validation)
        test = evaluate_model(
            model_name=best_name,
            estimator=calibrated_estimator,
            preprocessing=best.preprocessing,
            frame=split.test,
            config=self.config,
        )
        trained[best_name] = TrainedModel(
            model_name=best_name,
            estimator=calibrated_estimator,
            preprocessing=best.preprocessing,
            validation=best.validation,
            test=test,
            calibrated=calibrated,
        )

        root = Path(self.config.artifacts_root)
        model_reports: dict[str, dict[str, Any]] = {}
        best_path = root
        for model_name, item in trained.items():
            model_dir = model_artifact_dir(root, symbol, interval, target_name, model_name)
            evaluation = item.test if item.test is not None else item.validation
            metadata = {
                "symbol": symbol,
                "interval": interval,
                "target_name": target_name,
                "model_name": model_name,
                "feature_version": self.config.feature_version,
                "ml_engine_version": self.config.ml_engine_version,
                "sample_count": dataset.sample_count,
                "feature_count": len(dataset.feature_columns),
                "class_distribution": dataset.class_distribution,
                "is_best": model_name == best_name,
                "calibrated": item.calibrated,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            save_artifacts(
                directory=model_dir,
                model=item.estimator,
                preprocessing=item.preprocessing,
                feature_columns=dataset.feature_columns,
                metrics={
                    "classification": evaluation.metrics,
                    "operational": evaluation.operational_metrics,
                },
                confusion_matrix=evaluation.metrics.get("confusion_matrix", []),
                metadata=metadata,
            )
            model_reports[model_name] = compact_model_report(evaluation.metrics, evaluation.operational_metrics)
            if model_name == best_name:
                best_path = model_dir
                update_manifest(root, {**metadata, "artifact_dir": str(model_dir)})

        return TrainingReport(
            symbol=symbol,
            interval=interval,
            target_name=target_name,
            sample_count=dataset.sample_count,
            feature_count=len(dataset.feature_columns),
            class_distribution=dataset.class_distribution,
            model_reports=model_reports,
            best_model_name=best_name,
            best_model_path=best_path,
            generated_at=datetime.now(timezone.utc),
            manifest_entry={"artifact_dir": str(best_path)},
        )

    def walk_forward_validate(self, *, symbol: str, interval: str, target_name: str, windows: int = 3) -> list[dict[str, Any]]:
        dataset = self.repository.load_dataset(symbol=symbol, interval=interval, target_name=target_name)
        reports = []
        for index, split in enumerate(walk_forward_splits(dataset, windows=windows)):
            validate_training_data(split.train, min_class_count=self.config.min_class_count)
            preprocessing = fit_preprocessing(split.train, dataset.feature_columns)
            estimator = model_registry(self.config)["logistic_regression"]()
            estimator = train_estimator(estimator, preprocessing, split.train)
            validation = evaluate_model(
                model_name="logistic_regression",
                estimator=estimator,
                preprocessing=preprocessing,
                frame=split.validation,
                config=self.config,
            )
            reports.append({"window": index, "validation": validation.metrics})
        return reports


def run_initial_training() -> TrainingReport:
    settings = get_settings()
    engine = create_sync_engine(settings.database_url)
    try:
        repository = MLEngineRepository(engine)
        pipeline = MLEnginePipeline(repository)
        return pipeline.train_target(
            symbol="BTCUSDT",
            interval="5m",
            target_name="v2_long_tp_100bps_sl_50bps_h_24",
        )
    finally:
        engine.dispose()


def main() -> int:
    report = run_initial_training()
    print(f"{report.symbol} {report.interval} {report.target_name}")
    print(f"samples={report.sample_count} features={report.feature_count}")
    print(f"class_distribution={report.class_distribution}")
    print(f"best_model={report.best_model_name}")
    print(f"artifact_dir={report.best_model_path}")
    for model_name, model_report in report.model_reports.items():
        metrics = model_report["metrics"]
        print(
            f"{model_name}: "
            f"f1_macro={metrics.get('f1_macro')} "
            f"balanced_accuracy={metrics.get('balanced_accuracy')} "
            f"roc_auc={metrics.get('roc_auc')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
