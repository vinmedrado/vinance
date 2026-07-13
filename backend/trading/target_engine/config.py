from __future__ import annotations

from dataclasses import dataclass, field


TARGET_VERSION = "v2"


@dataclass(frozen=True)
class TargetSpec:
    side: str
    horizon_candles: int
    take_profit_pct: float
    stop_loss_pct: float

    def __post_init__(self) -> None:
        side = self.side.lower()
        if side not in {"long", "short"}:
            raise ValueError("side must be 'long' or 'short'")
        if self.horizon_candles <= 0:
            raise ValueError("horizon_candles must be positive")
        if self.take_profit_pct <= 0:
            raise ValueError("take_profit_pct must be positive")
        if self.stop_loss_pct <= 0:
            raise ValueError("stop_loss_pct must be positive")
        object.__setattr__(self, "side", side)

    @property
    def name(self) -> str:
        tp = _pct_token(self.take_profit_pct)
        sl = _pct_token(self.stop_loss_pct)
        return f"{TARGET_VERSION}_{self.side}_tp_{tp}_sl_{sl}_h_{self.horizon_candles}"


@dataclass(frozen=True)
class TargetEngineConfig:
    target_version: str = TARGET_VERSION
    default_limit: int = 100_000
    source_table: str = "crypto_candles"
    sink_table: str = "crypto_targets"
    specs: tuple[TargetSpec, ...] = field(
        default_factory=lambda: (
            TargetSpec("long", 12, 0.005, 0.005),
            TargetSpec("short", 12, 0.005, 0.005),
            TargetSpec("long", 24, 0.010, 0.005),
            TargetSpec("short", 24, 0.010, 0.005),
        )
    )


def _pct_token(value: float) -> str:
    basis_points = int(round(value * 10_000))
    return f"{basis_points}bps"


DEFAULT_CONFIG = TargetEngineConfig()
