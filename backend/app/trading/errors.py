from __future__ import annotations


class TradingDomainError(Exception):
    """Base class for safe, user-facing Trading product errors."""

    code = "TRADING_ERROR"
    status_code = 400


class TradingSchemaNotReadyError(TradingDomainError):
    code = "TRADING_SCHEMA_NOT_READY"
    status_code = 503


class TradingPaperOnlyError(TradingDomainError):
    code = "TRADING_PAPER_ONLY_REQUIRED"
    status_code = 409


class TradingNotFoundError(TradingDomainError):
    code = "TRADING_RESOURCE_NOT_FOUND"
    status_code = 404


class TradingConflictError(TradingDomainError):
    code = "TRADING_CONFLICT"
    status_code = 409


class TradingValidationError(TradingDomainError):
    code = "TRADING_VALIDATION_ERROR"
    status_code = 422


class TradingDataUnavailableError(TradingDomainError):
    code = "TRADING_DATA_UNAVAILABLE"
    status_code = 503
