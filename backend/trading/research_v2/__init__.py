"""Research and optimization engine for Backtesting V2 reports."""

from .config import ResearchConfig
from .models import ResearchResult
from .optimizer import ResearchOptimizer

__all__ = ["ResearchConfig", "ResearchOptimizer", "ResearchResult"]
