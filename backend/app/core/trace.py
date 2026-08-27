from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator


_decision_trace: ContextVar[dict[str, object]] = ContextVar("decision_trace", default={})


def current_trace_fields() -> dict[str, object]:
    """Return a copy so log records cannot mutate the active request context."""

    return dict(_decision_trace.get())


@contextmanager
def decision_trace_context(
    *,
    decision_id: str,
    correlation_id: str,
    user_id: int,
) -> Iterator[None]:
    token = _decision_trace.set(
        {
            "decision_id": decision_id,
            "correlation_id": correlation_id,
            "user_id": user_id,
        }
    )
    try:
        yield
    finally:
        _decision_trace.reset(token)
