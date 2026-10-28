from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any


class PromotionStatus(StrEnum):
    RESEARCH = "RESEARCH"
    VALIDATED = "VALIDATED"
    PAPER_CANDIDATE = "PAPER_CANDIDATE"
    PAPER_ACTIVE = "PAPER_ACTIVE"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


@dataclass(frozen=True)
class RegistryEntry:
    model_id: str
    version: str
    symbol: str
    interval: str
    target_version: str
    target_name: str
    feature_version: str
    model_name: str
    artifact_checksum: str
    created_at: str | None
    trained_until: str | None
    validation_status: str
    promotion_status: str
    metrics: dict[str, Any]
    artifact_dir: Path
    validation_run_id: str | None = None

    def public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("artifact_dir", None)
        payload["metrics"] = _public_metrics(self.metrics)
        return payload


def _numeric_tree(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return None
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, dict):
        return {
            str(key)[:80]: projected
            for key, item in list(value.items())[:100]
            if (projected := _numeric_tree(item, depth=depth + 1)) is not None
        }
    if isinstance(value, list):
        return [
            projected
            for item in value[:100]
            if (projected := _numeric_tree(item, depth=depth + 1)) is not None
        ]
    return None


def _public_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    allowed = {"classification", "operational"}
    return {
        key: projected
        for key in sorted(allowed)
        if key in metrics
        and (projected := _numeric_tree(metrics[key])) is not None
    }


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid Trading registry JSON: {path.name}") from exc


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_checksum(path: Path) -> str:
    required = (
        "model.joblib",
        "preprocessing.joblib",
        "feature_columns.json",
        "metadata.json",
    )
    digest = hashlib.sha256()
    for filename in required:
        artifact = path / filename
        if not artifact.is_file() or artifact.stat().st_size <= 0:
            raise RuntimeError(f"Missing Trading model artifact: {filename}")
        digest.update(filename.encode("utf-8"))
        digest.update(_file_sha256(artifact).encode("ascii"))
    return digest.hexdigest()


def _model_id(item: dict[str, Any]) -> str:
    identity = "|".join(
        str(item.get(key) or "")
        for key in (
            "symbol",
            "interval",
            "target_name",
            "model_name",
            "feature_version",
            "generated_at",
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]


class TradingModelRegistry:
    def __init__(
        self,
        *,
        artifacts_root: Path,
        promotion_manifest: Path,
        validation_root: Path,
    ) -> None:
        self.artifacts_root = artifacts_root.resolve()
        self.promotion_manifest = promotion_manifest
        self.validation_root = validation_root.resolve()
        self._cache_key: tuple[int, int, int, int] | None = None
        self._cache_entries: tuple[RegistryEntry, ...] = ()

    def _state_key(self) -> tuple[int, int, int, int]:
        research_path = self.artifacts_root / "manifest.json"
        research = research_path.stat() if research_path.is_file() else None
        try:
            promotions = self.promotion_manifest.stat()
        except OSError as exc:
            raise RuntimeError("Trading promotion manifest is unavailable") from exc
        return (
            research.st_mtime_ns if research else 0,
            research.st_size if research else 0,
            promotions.st_mtime_ns,
            promotions.st_size,
        )

    def _research_manifest(self) -> list[dict[str, Any]]:
        path = self.artifacts_root / "manifest.json"
        # Production images deliberately do not bundle the research artifact
        # tree.  An empty promotion manifest therefore represents a valid,
        # honest "no models promoted" state rather than an application crash.
        # Any promoted model still fails closed below because it cannot be
        # matched to a research artifact.
        if not path.is_file():
            return []
        payload = _read_json(path)
        models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(models, list):
            raise RuntimeError("Trading ML manifest must contain a models list")
        return [dict(item) for item in models if isinstance(item, dict)]

    def _promotions(self) -> dict[str, dict[str, Any]]:
        payload = _read_json(self.promotion_manifest)
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise RuntimeError("Trading promotion manifest version is unsupported")
        models = payload.get("models")
        if not isinstance(models, list):
            raise RuntimeError("Trading promotion manifest must contain a models list")
        promotions: dict[str, dict[str, Any]] = {}
        for item in models:
            if not isinstance(item, dict) or not item.get("model_id"):
                raise RuntimeError("Trading promotion manifest has an invalid entry")
            model_id = str(item["model_id"])
            if model_id in promotions:
                raise RuntimeError(f"Duplicate Trading model promotion: {model_id}")
            promotions[model_id] = dict(item)
        return promotions

    def _validation(self, promotion: dict[str, Any]) -> tuple[str, bool]:
        run_id = promotion.get("validation_run_id")
        if not run_id:
            return "NOT_VALIDATED", False
        if Path(str(run_id)).name != str(run_id):
            raise RuntimeError("Invalid Trading validation run identifier")
        run_dir = (self.validation_root / str(run_id)).resolve()
        if self.validation_root not in run_dir.parents:
            raise RuntimeError("Trading validation path escapes its root")
        summary_path = run_dir / "validation_summary.json"
        readiness_path = run_dir / "readiness.json"
        if not summary_path.is_file() or not readiness_path.is_file():
            return "EVIDENCE_MISSING", False
        summary = _read_json(summary_path)
        readiness = _read_json(readiness_path)
        ready = bool(
            isinstance(summary, dict)
            and summary.get("paper_trading_ready") is True
            and isinstance(readiness, dict)
            and readiness.get("paper_trading_ready") is True
        )
        return ("PAPER_READY" if ready else "NOT_PAPER_READY"), ready

    def list(self) -> list[RegistryEntry]:
        state_key = self._state_key()
        if self._cache_key == state_key:
            promotions = self._promotions()
            for entry in self._cache_entries:
                if entry.promotion_status == PromotionStatus.RESEARCH.value:
                    continue
                pinned = str(
                    promotions.get(entry.model_id, {}).get("artifact_checksum") or ""
                )
                if not pinned or pinned != _artifact_checksum(entry.artifact_dir):
                    raise RuntimeError(
                        f"Model {entry.model_id} promotion does not match the validated artifact checksum"
                    )
            return list(self._cache_entries)
        promotions = self._promotions()
        entries: list[RegistryEntry] = []
        known: set[str] = set()
        for item in self._research_manifest():
            model_id = _model_id(item)
            known.add(model_id)
            artifact_dir = Path(str(item.get("artifact_dir") or ""))
            if not artifact_dir.is_absolute():
                artifact_dir = (Path.cwd() / artifact_dir).resolve()
            if self.artifacts_root not in artifact_dir.parents:
                raise RuntimeError("Trading model artifact escapes the configured root")
            metadata = _read_json(artifact_dir / "metadata.json")
            metrics_path = artifact_dir / "metrics.json"
            metrics = _read_json(metrics_path) if metrics_path.is_file() else {}
            if not isinstance(metadata, dict) or not isinstance(metrics, dict):
                raise RuntimeError("Trading artifact metadata or metrics is invalid")
            promotion = promotions.get(model_id, {})
            try:
                status = PromotionStatus(str(promotion.get("promotion_status") or "RESEARCH"))
            except ValueError as exc:
                raise RuntimeError(f"Invalid Trading promotion status for {model_id}") from exc
            validation_status, paper_ready = self._validation(promotion)
            if status in {
                PromotionStatus.VALIDATED,
                PromotionStatus.PAPER_CANDIDATE,
                PromotionStatus.PAPER_ACTIVE,
            } and validation_status == "EVIDENCE_MISSING":
                raise RuntimeError(f"Model {model_id} has no validation evidence")
            if status is PromotionStatus.PAPER_ACTIVE and not paper_ready:
                raise RuntimeError(
                    f"Model {model_id} cannot be PAPER_ACTIVE: Validation V2 is not paper ready"
                )
            artifact_checksum = _artifact_checksum(artifact_dir)
            if status is not PromotionStatus.RESEARCH:
                pinned_checksum = str(promotion.get("artifact_checksum") or "")
                if not pinned_checksum or pinned_checksum != artifact_checksum:
                    raise RuntimeError(
                        f"Model {model_id} promotion does not match the validated artifact checksum"
                    )
            target_name = str(item.get("target_name") or metadata.get("target_name") or "")
            target_version = str(metadata.get("target_version") or target_name.split("_", 1)[0])
            version = str(
                metadata.get("model_version")
                or item.get("ml_engine_version")
                or item.get("generated_at")
                or model_id
            )
            entries.append(
                RegistryEntry(
                    model_id=model_id,
                    version=version,
                    symbol=str(item.get("symbol") or metadata.get("symbol") or ""),
                    interval=str(item.get("interval") or metadata.get("interval") or ""),
                    target_version=target_version,
                    target_name=target_name,
                    feature_version=str(
                        item.get("feature_version") or metadata.get("feature_version") or ""
                    ),
                    model_name=str(item.get("model_name") or metadata.get("model_name") or ""),
                    artifact_checksum=artifact_checksum,
                    created_at=item.get("generated_at") or metadata.get("created_at"),
                    trained_until=metadata.get("trained_until") or metadata.get("train_end"),
                    validation_status=validation_status,
                    promotion_status=status.value,
                    metrics={str(key): value for key, value in metrics.items()},
                    artifact_dir=artifact_dir,
                    validation_run_id=(
                        str(promotion["validation_run_id"])
                        if promotion.get("validation_run_id")
                        else None
                    ),
                )
            )
        unknown = sorted(set(promotions).difference(known))
        if unknown:
            raise RuntimeError(
                "Trading promotions reference missing artifacts: " + ", ".join(unknown)
            )
        resolved = sorted(
            entries,
            key=lambda item: (
                item.symbol,
                item.interval,
                item.target_name,
                item.model_name,
                item.created_at or "",
            ),
        )
        self._cache_key = state_key
        self._cache_entries = tuple(resolved)
        return list(resolved)

    def get(self, model_id: str) -> RegistryEntry | None:
        return next((entry for entry in self.list() if entry.model_id == model_id), None)

    def active(self) -> list[RegistryEntry]:
        return [
            entry
            for entry in self.list()
            if entry.promotion_status == PromotionStatus.PAPER_ACTIVE.value
        ]

    def health(self) -> dict[str, Any]:
        entries = self.list()
        active = [item for item in entries if item.promotion_status == "PAPER_ACTIVE"]
        candidates = [
            item for item in entries if item.promotion_status == "PAPER_CANDIDATE"
        ]
        return {
            "status": "PAPER_READY" if active else "NOT_PAPER_READY",
            "total": len(entries),
            "active": len(active),
            "candidates": len(candidates),
            "paper_trading_ready": bool(active),
            "continuous_scheduler_enabled": False,
        }

    def promote(
        self,
        *,
        model_id: str,
        status: PromotionStatus,
        validation_run_id: str | None,
        approved_by: str,
    ) -> dict[str, Any]:
        entries = {entry.model_id: entry for entry in self.list()}
        if model_id not in entries:
            raise LookupError("Trading model not found")
        candidate = {
            "model_id": model_id,
            "promotion_status": status.value,
            "validation_run_id": validation_run_id,
            "artifact_checksum": entries[model_id].artifact_checksum,
            "approved_by": approved_by,
            "approved_at": datetime.now(timezone.utc).isoformat(),
        }
        validation_status, paper_ready = self._validation(candidate)
        if status is PromotionStatus.PAPER_ACTIVE and not paper_ready:
            raise RuntimeError("Validation V2 does not authorize PAPER_ACTIVE")
        if status in {
            PromotionStatus.VALIDATED,
            PromotionStatus.PAPER_CANDIDATE,
        } and validation_status == "EVIDENCE_MISSING":
            raise RuntimeError("Validation evidence is required")
        payload = _read_json(self.promotion_manifest)
        models = [
            item
            for item in payload.get("models", [])
            if isinstance(item, dict) and str(item.get("model_id")) != model_id
        ]
        models.append(candidate)
        output = {"version": 1, "models": sorted(models, key=lambda item: item["model_id"])}
        temporary = self.promotion_manifest.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.promotion_manifest)
        self._cache_key = None
        self._cache_entries = ()
        return candidate


@lru_cache(maxsize=1)
def get_registry() -> TradingModelRegistry:
    root = Path(
        os.getenv("TRADING_ARTIFACTS_ROOT", "backend/trading/artifacts/ml_engine_v2")
    )
    manifest = Path(
        os.getenv(
            "TRADING_MODEL_REGISTRY_MANIFEST",
            "backend/trading/config/model_registry.json",
        )
    )
    validation = Path(
        os.getenv("TRADING_VALIDATION_ROOT", "backend/trading/output/validation_v2")
    )
    return TradingModelRegistry(
        artifacts_root=root,
        promotion_manifest=manifest,
        validation_root=validation,
    )
