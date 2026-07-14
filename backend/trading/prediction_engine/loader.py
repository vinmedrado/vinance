from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import joblib
import sklearn

from .config import DEFAULT_CONFIG, PredictionEngineConfig
from .errors import PredictionArtifactError, PredictionCompatibilityError
from .models import LoadedArtifacts, ManifestEntry


REQUIRED_ARTIFACT_FILES = (
    "model.joblib",
    "preprocessing.joblib",
    "feature_columns.json",
    "metadata.json",
)


class PredictionArtifactLoader:
    def __init__(self, config: PredictionEngineConfig = DEFAULT_CONFIG) -> None:
        self.config = config

    def load_manifest(self) -> dict[str, Any]:
        path = self.config.artifacts_root / "manifest.json"
        self._require_file(path, "manifest.json")
        manifest = self._read_json(path, "manifest.json")
        if not isinstance(manifest.get("models"), list):
            raise PredictionArtifactError(f"Invalid ML Engine V2 manifest: {path}; expected a 'models' list.")
        return manifest

    def select_best_model(self, *, symbol: str, interval: str, target_name: str) -> ManifestEntry:
        manifest = self.load_manifest()
        candidates = [
            item
            for item in manifest["models"]
            if item.get("symbol") == symbol
            and item.get("interval") == interval
            and item.get("target_name") == target_name
            and item.get("is_best") is True
        ]
        if not candidates:
            raise LookupError(f"No best model found for {symbol} {interval} {target_name}")
        selected = sorted(candidates, key=lambda item: str(item.get("generated_at", "")), reverse=True)[0]
        if selected.get("feature_version") != self.config.feature_version:
            raise PredictionArtifactError(
                "Best model feature_version does not match Prediction Engine config: "
                f"{selected.get('feature_version')} != {self.config.feature_version}"
            )
        return ManifestEntry(
            symbol=str(selected["symbol"]),
            interval=str(selected["interval"]),
            target_name=str(selected["target_name"]),
            model_name=str(selected["model_name"]),
            feature_version=str(selected["feature_version"]),
            ml_engine_version=str(selected.get("ml_engine_version", "")),
            is_best=bool(selected["is_best"]),
            artifact_dir=Path(selected["artifact_dir"]),
            generated_at=selected.get("generated_at"),
            metadata=dict(selected),
        )

    def load_artifacts(self, entry: ManifestEntry) -> LoadedArtifacts:
        artifact_dir = entry.artifact_dir
        if not artifact_dir.exists() or not artifact_dir.is_dir():
            raise PredictionArtifactError(f"Artifact directory not found: {artifact_dir}")
        for name in REQUIRED_ARTIFACT_FILES:
            self._require_file(artifact_dir / name, name)

        model = joblib.load(artifact_dir / "model.joblib")
        preprocessing = joblib.load(artifact_dir / "preprocessing.joblib")
        feature_columns_payload = self._read_json(artifact_dir / "feature_columns.json", "feature_columns.json")
        if not isinstance(feature_columns_payload, list) or not feature_columns_payload:
            raise PredictionArtifactError("feature_columns.json must contain a non-empty JSON list.")
        feature_columns = tuple(str(column) for column in feature_columns_payload)
        metadata = self._read_json(artifact_dir / "metadata.json", "metadata.json")
        if not isinstance(metadata, dict):
            raise PredictionArtifactError("metadata.json must contain a JSON object.")
        self._validate_artifact_contract(entry, preprocessing, feature_columns, metadata)
        return LoadedArtifacts(
            entry=entry,
            model=model,
            preprocessing=preprocessing,
            feature_columns=feature_columns,
            metadata=metadata,
        )

    def _validate_artifact_contract(
        self,
        entry: ManifestEntry,
        preprocessing: Any,
        feature_columns: tuple[str, ...],
        metadata: dict[str, Any],
    ) -> None:
        preprocessing_columns = tuple(getattr(preprocessing, "feature_columns", ()))
        if preprocessing_columns != feature_columns:
            raise PredictionArtifactError("feature_columns.json does not match preprocessing.feature_columns")
        for key in ("symbol", "interval", "target_name", "model_name", "feature_version"):
            if metadata.get(key) != getattr(entry, key):
                raise PredictionArtifactError(f"Artifact metadata mismatch for {key}: {metadata.get(key)} != {getattr(entry, key)}")
        if int(metadata.get("feature_count", -1)) != len(feature_columns):
            raise PredictionArtifactError("Artifact metadata feature_count does not match feature_columns.json")
        if metadata.get("feature_version") != self.config.feature_version:
            raise PredictionArtifactError(
                f"metadata.json feature_version must be {self.config.feature_version}; found {metadata.get('feature_version')}"
            )
        target_version = metadata.get("target_version", str(metadata.get("target_name", "")).split("_", 1)[0])
        if target_version != "v2":
            raise PredictionArtifactError(f"metadata.json target_version must be v2; found {target_version}")
        model_version = metadata.get("model_version") or metadata.get("ml_engine_version")
        if not model_version:
            raise PredictionArtifactError("metadata.json must contain model_version or ml_engine_version.")
        created_at = metadata.get("created_at") or metadata.get("generated_at")
        if not created_at:
            raise PredictionArtifactError("metadata.json must contain created_at or generated_at.")
        self._validate_checksums(entry.artifact_dir, metadata)
        self._validate_runtime_versions(metadata, entry.model_name)

    def _require_file(self, path: Path, label: str) -> None:
        if not path.exists():
            raise PredictionArtifactError(f"Required artifact file is missing: {label} ({path})")
        if not path.is_file():
            raise PredictionArtifactError(f"Required artifact path is not a file: {label} ({path})")
        if path.stat().st_size <= 0:
            raise PredictionArtifactError(f"Required artifact file is empty: {label} ({path})")

    def _read_json(self, path: Path, label: str) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PredictionArtifactError(f"Invalid JSON in {label} ({path}): {exc}") from exc

    def _validate_checksums(self, artifact_dir: Path, metadata: dict[str, Any]) -> None:
        checksums = metadata.get("checksums") or metadata.get("checksum")
        if checksums is None:
            return
        if not isinstance(checksums, dict):
            raise PredictionArtifactError("metadata checksum field must be an object when present.")
        for filename, expected in checksums.items():
            path = artifact_dir / str(filename)
            self._require_file(path, str(filename))
            found = hashlib.sha256(path.read_bytes()).hexdigest()
            if found != expected:
                raise PredictionArtifactError(
                    f"Checksum mismatch for {filename}: expected {expected}, found {found}."
                )

    def _validate_runtime_versions(self, metadata: dict[str, Any], model_name: str) -> None:
        expected_sklearn = metadata.get("sklearn_version")
        if expected_sklearn is not None and str(expected_sklearn) != sklearn.__version__:
            raise PredictionCompatibilityError(
                dependency="sklearn",
                expected=str(expected_sklearn),
                found=sklearn.__version__,
                model_name=model_name,
            )
        expected_xgboost = metadata.get("xgboost_version")
        if expected_xgboost is not None:
            try:
                import xgboost
            except Exception as exc:
                raise PredictionCompatibilityError(
                    dependency="xgboost",
                    expected=str(expected_xgboost),
                    found="not installed",
                    model_name=model_name,
                ) from exc
            if str(expected_xgboost) != xgboost.__version__:
                raise PredictionCompatibilityError(
                    dependency="xgboost",
                    expected=str(expected_xgboost),
                    found=xgboost.__version__,
                    model_name=model_name,
                )
