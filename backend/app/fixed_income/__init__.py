"""Canonical fixed-income suitability adapter."""

from backend.app.fixed_income.engine import evaluate_fixed_income_product
from backend.app.fixed_income.rules import ENGINE_VERSION, RULES_VERSION

__all__ = ["ENGINE_VERSION", "RULES_VERSION", "evaluate_fixed_income_product"]
