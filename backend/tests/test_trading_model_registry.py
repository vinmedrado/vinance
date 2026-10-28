from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.trading.model_registry import PromotionStatus, TradingModelRegistry


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _registry(tmp_path: Path) -> tuple[TradingModelRegistry, str, Path]:
    artifact_root = tmp_path / "artifacts"
    artifact = artifact_root / "BTCUSDT" / "5m" / "target" / "model"
    artifact.mkdir(parents=True)
    (artifact / "model.joblib").write_bytes(b"model")
    (artifact / "preprocessing.joblib").write_bytes(b"preprocessing")
    _write_json(artifact / "feature_columns.json", ["feature"])
    _write_json(
        artifact / "metadata.json",
        {
            "symbol": "BTCUSDT",
            "interval": "5m",
            "target_name": "v2_long_tp_100bps_sl_50bps_h_24",
            "model_name": "extra_trees",
            "feature_version": "v2",
            "generated_at": "2026-01-01T00:00:00+00:00",
        },
    )
    _write_json(
        artifact / "metrics.json",
        {
            "classification": {"accuracy": 0.5, "private_path": "C:/private"},
            "operational": {"majority_baseline": {"accuracy": 0.6}},
            "api_key": "must-not-leak",
        },
    )
    _write_json(
        artifact_root / "manifest.json",
        {
            "models": [
                {
                    "symbol": "BTCUSDT",
                    "interval": "5m",
                    "target_name": "v2_long_tp_100bps_sl_50bps_h_24",
                    "model_name": "extra_trees",
                    "feature_version": "v2",
                    "ml_engine_version": "v2",
                    "generated_at": "2026-01-01T00:00:00+00:00",
                    "artifact_dir": str(artifact),
                }
            ]
        },
    )
    promotions = tmp_path / "registry.json"
    _write_json(promotions, {"version": 1, "models": []})
    validation_root = tmp_path / "validation"
    registry = TradingModelRegistry(
        artifacts_root=artifact_root,
        promotion_manifest=promotions,
        validation_root=validation_root,
    )
    model_id = registry.list()[0].model_id
    return registry, model_id, validation_root


def test_registry_defaults_every_artifact_to_research(tmp_path: Path) -> None:
    registry, _, _ = _registry(tmp_path)
    entry = registry.list()[0]
    assert entry.promotion_status == "RESEARCH"
    assert entry.validation_status == "NOT_VALIDATED"
    assert registry.health()["paper_trading_ready"] is False
    assert entry.artifact_checksum
    assert "artifact_dir" not in entry.public_dict()
    assert "api_key" not in entry.public_dict()["metrics"]
    assert "private_path" not in entry.public_dict()["metrics"]["classification"]


def test_registry_allows_production_image_without_research_artifacts_when_nothing_is_promoted(
    tmp_path: Path,
) -> None:
    promotions = tmp_path / "registry.json"
    _write_json(promotions, {"version": 1, "models": []})
    registry = TradingModelRegistry(
        artifacts_root=tmp_path / "excluded-research-artifacts",
        promotion_manifest=promotions,
        validation_root=tmp_path / "validation",
    )

    assert registry.list() == []
    assert registry.health()["status"] == "NOT_PAPER_READY"
    assert registry.health()["paper_trading_ready"] is False


def test_registry_fails_closed_when_a_promotion_has_no_artifact(tmp_path: Path) -> None:
    promotions = tmp_path / "registry.json"
    _write_json(
        promotions,
        {
            "version": 1,
            "models": [
                {
                    "model_id": "missing-model",
                    "promotion_status": "PAPER_CANDIDATE",
                    "validation_run_id": "missing-validation",
                }
            ],
        },
    )
    registry = TradingModelRegistry(
        artifacts_root=tmp_path / "excluded-research-artifacts",
        promotion_manifest=promotions,
        validation_root=tmp_path / "validation",
    )

    with pytest.raises(RuntimeError, match="missing artifacts"):
        registry.list()


def test_registry_rejects_paper_active_without_validation_v2_readiness(
    tmp_path: Path,
) -> None:
    registry, model_id, validation_root = _registry(tmp_path)
    run = validation_root / "not-ready"
    _write_json(run / "validation_summary.json", {"paper_trading_ready": False})
    _write_json(run / "readiness.json", {"paper_trading_ready": False})
    with pytest.raises(RuntimeError, match="does not authorize"):
        registry.promote(
            model_id=model_id,
            status=PromotionStatus.PAPER_ACTIVE,
            validation_run_id="not-ready",
            approved_by="test-reviewer",
        )
    assert registry.health()["active"] == 0


def test_registry_allows_explicit_candidate_but_never_auto_activates(
    tmp_path: Path,
) -> None:
    registry, model_id, validation_root = _registry(tmp_path)
    run = validation_root / "candidate-review"
    _write_json(run / "validation_summary.json", {"paper_trading_ready": False})
    _write_json(run / "readiness.json", {"paper_trading_ready": False})
    _write_json(
        registry.promotion_manifest,
        {
            "version": 1,
            "models": [
                {
                    "model_id": model_id,
                    "promotion_status": PromotionStatus.PAPER_CANDIDATE.value,
                    "validation_run_id": "candidate-review",
                    "artifact_checksum": registry.get(model_id).artifact_checksum,
                    "approved_by": "test-reviewer",
                }
            ],
        },
    )
    registry._cache_key = None
    assert registry.get(model_id).promotion_status == "PAPER_CANDIDATE"
    assert registry.health()["active"] == 0


def test_registry_detects_artifact_change_after_promotion_and_cache_warmup(
    tmp_path: Path,
) -> None:
    registry, model_id, validation_root = _registry(tmp_path)
    run = validation_root / "candidate-review"
    _write_json(run / "validation_summary.json", {"paper_trading_ready": False})
    _write_json(run / "readiness.json", {"paper_trading_ready": False})
    registry.promote(
        model_id=model_id,
        status=PromotionStatus.PAPER_CANDIDATE,
        validation_run_id="candidate-review",
        approved_by="test-reviewer",
    )
    entry = registry.get(model_id)
    assert entry is not None
    (entry.artifact_dir / "model.joblib").write_bytes(b"changed-after-review")

    with pytest.raises(RuntimeError, match="artifact checksum"):
        registry.list()
