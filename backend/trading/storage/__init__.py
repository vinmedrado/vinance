from .database import create_sync_engine

__all__ = ("LATEST_TRADING_SCHEMA_VERSION", "create_sync_engine")


def __getattr__(name: str):
    # Keep ``python -m backend.trading.storage.migrate`` free from runpy's
    # double-import warning while preserving the package-level convenience
    # export for callers.
    if name == "LATEST_TRADING_SCHEMA_VERSION":
        from .migrate import LATEST_TRADING_SCHEMA_VERSION

        return LATEST_TRADING_SCHEMA_VERSION
    raise AttributeError(name)
