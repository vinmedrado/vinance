from __future__ import annotations

import asyncio
from datetime import datetime
from collections.abc import Sequence
from typing import Any

import httpx
try:
    from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
except ImportError:  # pragma: no cover - fallback only for minimal validation envs
    def retry(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    def retry_if_exception_type(*args, **kwargs):
        return None

    def stop_after_attempt(*args, **kwargs):
        return None

    def wait_exponential(*args, **kwargs):
        return None

from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class MarketProviderError(RuntimeError):
    """Controlled provider error used to avoid breaking scheduler tasks."""


class ProviderRateLimitError(MarketProviderError):
    """Raised when Brapi answers with HTTP 429."""


class ProviderHTTPStatusError(MarketProviderError):
    """Raised for non-retryable Brapi HTTP status codes."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(message)


class BrapiClient:
    """Async Brapi client for B3 quotes and historical prices.

    The client is intentionally small: no scraping, no hidden side effects and no
    direct database writes. Services own normalization/persistence.
    """

    base_url = "https://brapi.dev/api"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 15.0,
        max_concurrency: int = 4,
        min_interval_seconds: float = 0.25,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.brapi_api_key
        self.timeout = httpx.Timeout(timeout_seconds)
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._min_interval_seconds = max(0.0, min_interval_seconds)

    def _params(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        params = dict(extra or {})
        if self.api_key:
            params["token"] = self.api_key
        return params

    async def _throttle(self) -> None:
        if self._min_interval_seconds:
            await asyncio.sleep(self._min_interval_seconds)

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError, ProviderRateLimitError)),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with self._semaphore:
            await self._throttle()
            url = f"{self.base_url}{path}"
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, params=self._params(params))
                if response.status_code == 429:
                    logger.warning("Brapi rate limit reached", extra={"path": path})
                    raise ProviderRateLimitError("Brapi rate limit reached")
                if response.status_code >= 400:
                    logger.warning("Brapi returned HTTP error", extra={"path": path, "status_code": response.status_code})
                    raise ProviderHTTPStatusError(response.status_code, f"Brapi HTTP {response.status_code}")
                data = response.json()
                return data if isinstance(data, dict) else {"results": data}
            except (httpx.TimeoutException, httpx.TransportError, ProviderRateLimitError, ProviderHTTPStatusError):
                raise
            except Exception as exc:  # noqa: BLE001 - provider failures are controlled here
                logger.warning("Brapi request failed", extra={"path": path, "error": str(exc)})
                raise MarketProviderError(str(exc)) from exc

    async def safe_get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            return await self._get(path, params=params)
        except ProviderHTTPStatusError as exc:
            logger.warning("Brapi safe fallback", extra={"path": path, "status_code": exc.status_code, "error": str(exc)})
            return {"results": [], "error": str(exc), "status_code": exc.status_code}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Brapi safe fallback", extra={"path": path, "error": str(exc)})
            return {"results": [], "error": str(exc)}

    async def get_quotes(self, tickers: Sequence[str]) -> dict[str, Any]:
        clean = [ticker.strip().upper() for ticker in tickers if ticker and ticker.strip()]
        if not clean:
            return {"results": []}
        return await self.safe_get(f"/quote/{','.join(clean)}")

    async def get_historical_quotes(self, ticker: str, range: str = "3mo") -> dict[str, Any]:  # noqa: A002 - Brapi API uses range
        clean = ticker.strip().upper()
        if not clean:
            return {"results": []}
        return await self.safe_get(f"/quote/{clean}", params={"range": range, "interval": "1d"})

    async def get_available_tickers(self) -> dict[str, Any]:
        return await self.safe_get("/available")


class BrapiProvider:
    """Synchronous BRAPI quote provider for current B3 prices.

    This provider has no database side effects. It only fetches and normalizes
    quote payloads for the service/task layer to consume later.
    """

    base_url = "https://brapi.dev/api/quote"
    batch_size = 20

    def __init__(self, *, token: str | None = None, timeout: float = 15.0) -> None:
        self.token = token if token is not None else self._settings_token()
        self.timeout = timeout

    @staticmethod
    def _settings_token() -> str | None:
        # Prefer the audit contract name, but keep compatibility with earlier
        # lowercase settings used in the market module.
        return (
            getattr(settings, "BRAPI_TOKEN", None)
            or getattr(settings, "brapi_token", None)
            or getattr(settings, "brapi_api_key", None)
        )

    @staticmethod
    def _clean_ticker(ticker: str) -> str:
        return str(ticker or "").strip().upper().replace(".SA", "")

    def _batches(self, tickers: list[str]) -> list[list[str]]:
        clean: list[str] = []
        seen: set[str] = set()
        for ticker in tickers:
            normalized = self._clean_ticker(ticker)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            clean.append(normalized)
        return [clean[index : index + self.batch_size] for index in range(0, len(clean), self.batch_size)]

    def _params(self) -> dict[str, str]:
        return {"token": self.token} if self.token else {}

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError, ProviderRateLimitError)),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _fetch_batch(self, batch: list[str]) -> dict[str, Any]:
        url = f"{self.base_url}/{','.join(batch)}"
        logger.info("BRAPI quote batch request started", extra={"tickers": batch, "batch_size": len(batch)})
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=self._params())
        except httpx.TimeoutException:
            logger.warning("BRAPI quote batch timed out", extra={"tickers": batch})
            raise
        except httpx.TransportError as exc:
            logger.warning("BRAPI quote transport error", extra={"tickers": batch, "error": str(exc)})
            raise

        if response.status_code == 429:
            logger.warning("BRAPI rate limit reached", extra={"tickers": batch, "status_code": response.status_code})
            raise ProviderRateLimitError("BRAPI rate limit reached")
        if response.status_code >= 400:
            logger.warning("BRAPI quote batch HTTP error", extra={"tickers": batch, "status_code": response.status_code})
            return {"results": []}

        try:
            payload = response.json()
        except ValueError as exc:
            logger.error("BRAPI returned invalid JSON", extra={"tickers": batch, "error": str(exc)})
            return {"results": []}

        if not isinstance(payload, dict):
            logger.warning("BRAPI returned non-dict payload", extra={"tickers": batch, "payload_type": type(payload).__name__})
            return {"results": []}
        return payload

    def fetch_quotes(self, tickers: list[str]) -> list[dict[str, Any]]:
        """Fetch and normalize quotes in batches of up to 20 tickers."""
        if not tickers:
            logger.info("BRAPI fetch_quotes called without tickers")
            return []

        normalized: list[dict[str, Any]] = []
        for batch in self._batches(tickers):
            try:
                payload = self._fetch_batch(batch)
            except Exception as exc:  # noqa: BLE001 - provider must fail closed
                logger.error("BRAPI quote batch failed", extra={"tickers": batch, "error": str(exc)})
                continue

            results = payload.get("results") or []
            if not isinstance(results, list) or not results:
                logger.warning("BRAPI quote batch returned empty payload", extra={"tickers": batch})
                continue

            for item in results:
                quote = self._normalize_quote(item if isinstance(item, dict) else {})
                if quote is None:
                    logger.warning("BRAPI quote ignored during normalization", extra={"payload": item})
                    continue
                normalized.append(quote)

        logger.info("BRAPI fetch_quotes finished", extra={"requested": len(tickers), "returned": len(normalized)})
        return normalized

    def _normalize_quote(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        ticker = self._clean_ticker(str(_first_not_none(payload.get("symbol"), payload.get("ticker"), "")))
        price = _float_or_none(_first_not_none(payload.get("regularMarketPrice"), payload.get("price")))

        if not ticker or price is None:
            return None

        return {
            "ticker": ticker,
            "price": price,
            "change_percent": _float_or_none(_first_not_none(payload.get("regularMarketChangePercent"), payload.get("change_percent"))),
            "volume": _int_or_none(_first_not_none(payload.get("regularMarketVolume"), payload.get("volume"))),
            "market_cap": _int_or_none(_first_not_none(payload.get("marketCap"), payload.get("market_cap"))),
            "updated_at": datetime.utcnow(),
        }


def _first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
