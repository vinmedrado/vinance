"""Compatibility wrapper.

A regra financeira pura fica em app.domain.finance.calculator.
Este módulo existe para não quebrar imports antigos.
"""
from backend.app.domain.finance.calculator import *  # noqa: F401,F403
