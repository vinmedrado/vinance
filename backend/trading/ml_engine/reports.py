from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .serialization import read_json, write_json


def update_manifest(root: Path, entry: dict[str, Any]) -> Path:
    path = root / "manifest.json"
    if path.exists():
        manifest = read_json(path)
    else:
        manifest = {"generated_at": None, "models": []}
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    models = [
        item
        for item in manifest.get("models", [])
        if not (
            item.get("symbol") == entry.get("symbol")
            and item.get("interval") == entry.get("interval")
            and item.get("target_name") == entry.get("target_name")
            and item.get("model_name") == entry.get("model_name")
        )
    ]
    models.append(entry)
    manifest["models"] = sorted(models, key=lambda item: (item.get("symbol", ""), item.get("target_name", ""), item.get("model_name", "")))
    write_json(path, manifest)
    return path


def compact_model_report(metrics: dict[str, Any], operational_metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "metrics": metrics,
        "operational_metrics": operational_metrics,
    }
