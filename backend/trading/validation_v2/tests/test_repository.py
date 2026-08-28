from __future__ import annotations

import json

from backend.trading.validation_v2.config import ValidationConfig
from backend.trading.validation_v2.repository import ValidationRepository

from .helpers import validation_fixture


def _config(paths) -> ValidationConfig:
    return ValidationConfig(
        manifest_path=paths["manifest"],
        backtesting_output_root=paths["backtests"],
        research_output_root=paths["research"],
        output_root=paths["output"],
    )


def test_repository_reads_and_pairs_backtesting_and_research_reports(tmp_path) -> None:
    paths = validation_fixture(tmp_path)
    inputs = ValidationRepository(_config(paths)).load()

    assert len(inputs.artifacts) == 3
    assert len(inputs.cases) == 3
    assert all(case.source_research_run_id.startswith("research-") for case in inputs.cases)
    assert inputs.coverage["validated_combinations"] == 3


def test_multiasset_multitarget_and_multimodel_discovery(tmp_path) -> None:
    paths = validation_fixture(tmp_path)
    coverage = ValidationRepository(_config(paths)).load().coverage

    assert coverage["validated_assets"] == ["BTCUSDT", "ETHUSDT"]
    assert coverage["validated_targets"] == ["target_a", "target_b"]
    assert coverage["validated_models"] == ["hist_gradient_boosting", "random_forest"]
    assert len(coverage["validated_periods"]) == 2


def test_artifact_without_reports_is_recorded_not_executed(tmp_path) -> None:
    paths = validation_fixture(tmp_path)
    manifest = json.loads(paths["manifest"].read_text())
    manifest["models"].append({"symbol": "SOLUSDT", "interval": "5m", "target_name": "target_c", "model_name": "xgboost", "artifact_dir": "x", "is_best": False})
    paths["manifest"].write_text(json.dumps(manifest))

    inputs = ValidationRepository(_config(paths)).load()

    assert len(inputs.cases) == 3
    assert any(row["symbol"] == "SOLUSDT" for row in inputs.coverage["missing_artifact_reports"])
