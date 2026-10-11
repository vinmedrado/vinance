"""Retired import location.

Fixed-income suitability is owned exclusively by ``backend.app.fixed_income``.
This module intentionally contains no engine, heuristics or defaults.
"""

from backend.app.fixed_income.engine import evaluate_fixed_income_product

__all__ = ["evaluate_fixed_income_product"]
