from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ARTIFACTS_DIR = Path("data/ml_artifacts")


def ensure_artifacts_dir() -> Path:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    gitkeep = ARTIFACTS_DIR / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("", encoding="utf-8")
    return ARTIFACTS_DIR


def _safe_market(market: str) -> str:
    return "".join(ch for ch in market.lower() if ch.isalnum() or ch in {"_", "-"})


def artifact_prefix(*, market: str, horizon_days: int, trained_at: str | None = None) -> str:
    stamp = trained_at or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{_safe_market(market)}_{horizon_days}d_{stamp}"


def save_model(model: Any, *, market: str, horizon_days: int, metadata: dict[str, Any]) -> dict[str, str]:
    try:
        import joblib
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError("joblib/scikit-learn não disponível para salvar modelo") from exc

    artifacts_dir = ensure_artifacts_dir()
    trained_at = metadata.get("trained_at") or datetime.now(timezone.utc).isoformat()
    prefix = artifact_prefix(market=market, horizon_days=horizon_days, trained_at=trained_at.replace(":", "").replace("-", "")[:15])
    model_path = artifacts_dir / f"{prefix}.joblib"
    metadata_path = artifacts_dir / f"{prefix}.metadata.json"
    joblib.dump(model, model_path)
    metadata_payload = {**metadata, "market": market, "horizon_days": horizon_days, "model_path": str(model_path)}
    metadata_path.write_text(json.dumps(metadata_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {"model_path": str(model_path), "metadata_path": str(metadata_path)}


def list_model_metadata(*, market: str | None = None, horizon_days: int | None = None) -> list[dict[str, Any]]:
    artifacts_dir = ensure_artifacts_dir()
    models: list[dict[str, Any]] = []
    for metadata_file in sorted(artifacts_dir.glob("*.metadata.json"), reverse=True):
        try:
            payload = json.loads(metadata_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if market and payload.get("market") != market:
            continue
        if horizon_days and int(payload.get("horizon_days") or 0) != horizon_days:
            continue
        payload["metadata_path"] = str(metadata_file)
        models.append(payload)
    return models


def latest_model_metadata(*, market: str, horizon_days: int | None = None) -> dict[str, Any] | None:
    candidates = list_model_metadata(market=market, horizon_days=horizon_days)
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: str(item.get("trained_at") or ""), reverse=True)[0]


def load_model(*, market: str, horizon_days: int | None = None) -> tuple[Any | None, dict[str, Any] | None]:
    metadata = latest_model_metadata(market=market, horizon_days=horizon_days)
    if not metadata:
        return None, None
    model_path = metadata.get("model_path")
    if not model_path or not Path(model_path).exists():
        return None, metadata
    try:
        import joblib
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError("joblib/scikit-learn não disponível para carregar modelo") from exc
    return joblib.load(model_path), metadata
