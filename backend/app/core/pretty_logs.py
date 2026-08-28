from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def _format_key(key: str) -> str:
    return key.replace("_", " ").strip().title()


def _format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value)
    return str(value)


def _emit(logger: Any, level: str, icon: str, title: str, payload: Mapping[str, Any] | None = None) -> None:
    lines = [f"{icon} {title}"]
    for key, value in (payload or {}).items():
        lines.append(f"   {_format_key(str(key))}: {_format_value(value)}")
    message = "\n".join(lines)
    log_fn = getattr(logger, level, logger.info)
    log_fn(message)


def log_task_start(logger: Any, title: str, **payload: Any) -> None:
    _emit(logger, "info", "🚀", title, payload)


def log_task_success(logger: Any, title: str, **payload: Any) -> None:
    _emit(logger, "info", "✅", title, payload)


def log_task_warning(logger: Any, title: str, **payload: Any) -> None:
    _emit(logger, "warning", "⚠️", title, payload)


def log_task_error(logger: Any, title: str, **payload: Any) -> None:
    _emit(logger, "error", "❌", title, payload)


def log_section(logger: Any, title: str, lines: Iterable[str]) -> None:
    message_lines = [f"📌 {title}"]
    message_lines.extend(f"   {line}" for line in lines)
    logger.info("\n".join(message_lines))
