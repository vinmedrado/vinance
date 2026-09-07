from __future__ import annotations

from collections.abc import Mapping
from typing import Any


# Trading V2 owns these tables through backend/trading/storage/schema.sql.
# They share PostgreSQL's public schema with the application, but are not part
# of the main ORM/Alembic metadata lifecycle.
TRADING_EXTERNAL_TABLES = frozenset(
    {
        "backtest_runs",
        "crypto_candles",
        "crypto_features",
        "crypto_targets",
        "paper_trades",
        "trading_signals",
    }
)


def include_name(
    name: str | None,
    type_: str,
    parent_names: Mapping[str, Any],
) -> bool:
    """Keep Trading V2's explicit SQL schema outside Alembic autogenerate."""

    del parent_names
    return not (type_ == "table" and name in TRADING_EXTERNAL_TABLES)
