from __future__ import annotations

from decimal import Decimal


EVALUATION_POLICY_VERSION = "decision-performance-v1"

# Calendar-day horizons. A daily bar is observable only at conservative UTC EOD.
HORIZON_DAYS: dict[str, int] = {"1d": 1, "7d": 7, "30d": 30}
REFERENCE_PRICE_TOLERANCE_DAYS = 3
EVALUATION_PRICE_TOLERANCE_DAYS = 4
PRICE_SOURCE_PRIORITY = ("brapi", "coingecko", "yfinance")

# Classification belongs to Phase 36 and does not change recommendation scores.
NEUTRAL_RETURN_THRESHOLD_PCT = Decimal("1")
STRONG_RETURN_THRESHOLD_PCT = Decimal("5")

CONFIDENCE_BANDS: tuple[tuple[str, Decimal, Decimal | None], ...] = (
    ("LOW", Decimal("0"), Decimal("60")),
    ("MEDIUM", Decimal("60"), Decimal("80")),
    ("HIGH", Decimal("80"), None),
)
SCORE_BANDS: tuple[tuple[str, Decimal, Decimal | None], ...] = (
    ("LOW", Decimal("0"), Decimal("60")),
    ("MEDIUM", Decimal("60"), Decimal("75")),
    ("HIGH", Decimal("75"), None),
)

CALIBRATION_MIN_SAMPLE = 5
CALIBRATION_GAP_TOLERANCE_PCT = Decimal("10")
CALIBRATION_STRONG_GAP_PCT = Decimal("15")
