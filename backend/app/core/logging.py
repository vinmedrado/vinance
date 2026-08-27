from __future__ import annotations

import logging
import json
import re
import sys
from datetime import datetime, timezone

from backend.app.core.config import settings
from backend.app.core.trace import current_trace_fields


_STRUCTURED_FIELDS = (
    "event",
    "decision_id",
    "correlation_id",
    "user_id",
    "asset",
    "status",
    "latency_ms",
    "fallback_used",
    "error_code",
    "audit_status",
    "exception_type",
    "subscription_id",
    "alert_id",
    "alert_type",
    "severity",
    "evaluations",
    "alerts_generated",
    "cooldown_suppressed",
    "duplicates_prevented",
    "errors",
)
_BEARER_PATTERN = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")
_SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)(\b(?:authorization|access[_-]?token|refresh[_-]?token|password|cookie|api[_-]?key|secret)\b"
    r"[\"']?\s*[:=]\s*)(?:[\"'][^\"']*[\"']|[^,\s}\]]+)"
)


def _safe_log_text(value: object) -> str:
    redacted = _BEARER_PATTERN.sub("Bearer [REDACTED]", str(value))
    return _SENSITIVE_VALUE_PATTERN.sub(r"\1[REDACTED]", redacted)


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _safe_log_text(record.getMessage()),
        }
        trace_fields = current_trace_fields()
        for field in _STRUCTURED_FIELDS:
            value = getattr(record, field, trace_fields.get(field))
            if value not in (None, ""):
                payload[field] = _safe_log_text(value) if isinstance(value, str) else value
        return json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))


def configure_logging() -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING if settings.is_production else logging.INFO)

    # FASE 29: keep runtime logs clean while preserving real warnings/errors.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
