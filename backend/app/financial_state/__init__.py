"""Canonical household financial state domain."""

from backend.app.financial_state.engine import ENGINE_VERSION, calculate_financial_state

__all__ = ["ENGINE_VERSION", "calculate_financial_state"]
