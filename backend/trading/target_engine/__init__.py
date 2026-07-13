"""Target Engine V2 for trading model labels."""

from .builder import TargetBuilder, build_targets_v2
from .config import DEFAULT_CONFIG, TARGET_VERSION

__all__ = ["DEFAULT_CONFIG", "TARGET_VERSION", "TargetBuilder", "build_targets_v2"]
