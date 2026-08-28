from __future__ import annotations

import json
import math
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


class ExpansionReportWriter:
    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root
        self.output_root.mkdir(parents=True, exist_ok=True)

    def write(self, name: str, payload: Any) -> Path:
        path = self.output_root / f"{name}.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(_sanitize(payload), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
        temporary.replace(path)
        return path


def _sanitize(value: Any) -> Any:
    if is_dataclass(value):
        return _sanitize(asdict(value))
    if isinstance(value, dict):
        return {str(key): _sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return _sanitize(value.item())
    return value
