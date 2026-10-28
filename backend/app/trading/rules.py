from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.trading.paper_trading_v2.config import DEFAULT_CONFIG


TRADING_PRODUCT_RULESET_VERSION = "trading-assisted-paper-v1"


@dataclass(frozen=True)
class TradingProductRules:
    ruleset_version: str = TRADING_PRODUCT_RULESET_VERSION
    quote_asset: str = "USDT"
    default_virtual_balance: Decimal = Decimal(str(DEFAULT_CONFIG.initial_capital))
    minimum_virtual_balance: Decimal = Decimal("100.00")
    maximum_virtual_balance: Decimal = Decimal("1000000.00")
    supported_market: str = "CRYPTO"
    supported_intervals: tuple[str, ...] = ("5m",)
    # The existing engine operates on five-minute candles.  An interactive
    # Paper action must not use a reference older than three completed bars.
    # This is intentionally a product ruleset value (and is snapshotted on the
    # order), rather than an implicit query default.
    reference_price_max_age_seconds: int = 15 * 60
    supported_symbols: tuple[str, ...] = (
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "SOLUSDT",
        "XRPUSDT",
    )
    # Interactive V1 supports the existing engine's long-only contract.
    supported_open_sides: tuple[str, ...] = ("BUY",)


RULES = TradingProductRules()
