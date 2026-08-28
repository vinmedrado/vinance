from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


RESEARCH_ENGINE_VERSION = "v2"


@dataclass(frozen=True)
class ResearchConfig:
    engine_version: str = RESEARCH_ENGINE_VERSION
    backtesting_output_root: Path = Path("backend/trading/output/backtesting_v2")
    output_root: Path = Path("backend/trading/output/research_v2")
    backtest_run_id: str | None = None
    monte_carlo_simulations: int = 1_000
    bootstrap_iterations: int = 1_000
    confidence_level: float = 0.95
    seed: int = 42
    minimum_trades: int = 30
    overwrite: bool = True
    paper_only: bool = True

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise RuntimeError("Research V2 requires PAPER_ONLY=True.")
        if self.monte_carlo_simulations < 100:
            raise ValueError("monte_carlo_simulations must be at least 100")
        if self.bootstrap_iterations < 100:
            raise ValueError("bootstrap_iterations must be at least 100")
        if not 0.50 < self.confidence_level < 1.0:
            raise ValueError("confidence_level must be between 0.50 and 1.0")
        if self.minimum_trades < 1:
            raise ValueError("minimum_trades must be positive")

    def deterministic_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("output_root", None)
        payload.pop("backtesting_output_root", None)
        payload.pop("overwrite", None)
        payload["engine_version"] = self.engine_version
        return payload
