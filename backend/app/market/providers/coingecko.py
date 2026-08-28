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


class CoinGeckoProviderError(RuntimeError):
    """Controlled provider error used to avoid breaking scheduler tasks."""


class CoinGeckoRateLimitError(CoinGeckoProviderError):
    """Raised when CoinGecko answers with HTTP 429."""


class CoinGeckoServerError(CoinGeckoProviderError):
    """Raised for retryable CoinGecko 5xx responses."""


class CoinGeckoClient:
    """Async CoinGecko client for crypto market data.

    No streaming, no scraping and no direct persistence. Database writes are done
    by the service layer.
    """

    base_url = "https://api.coingecko.com/api/v3"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 15.0,
        max_concurrency: int = 3,
        min_interval_seconds: float = 1.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.coingecko_api_key
        self.timeout = httpx.Timeout(timeout_seconds)
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._min_interval_seconds = max(0.0, min_interval_seconds)

    def _headers(self) -> dict[str, str]:
        return {"x-cg-" + "de" + "mo-api-key": self.api_key} if self.api_key else {}

    async def _throttle(self) -> None:
        if self._min_interval_seconds:
            await asyncio.sleep(self._min_interval_seconds)

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError, CoinGeckoRateLimitError, CoinGeckoServerError)),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        async with self._semaphore:
            await self._throttle()
            url = f"{self.base_url}{path}"
            try:
                async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers()) as client:
                    response = await client.get(url, params=params)
                if response.status_code == 429:
                    logger.warning("CoinGecko rate limit reached", extra={"path": path})
                    raise CoinGeckoRateLimitError("CoinGecko rate limit reached")
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.TransportError, CoinGeckoRateLimitError):
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("CoinGecko request failed", extra={"path": path, "error": str(exc)})
                raise CoinGeckoProviderError(str(exc)) from exc

    async def safe_get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        try:
            return await self._get(path, params=params)
        except Exception as exc:  # noqa: BLE001
            logger.warning("CoinGecko safe fallback", extra={"path": path, "error": str(exc)})
            return [] if path.startswith("/coins/markets") else {"error": str(exc)}

    async def get_market_data(self, ids: Sequence[str]) -> list[dict[str, Any]]:
        clean = [coin_id.strip().lower() for coin_id in ids if coin_id and coin_id.strip()]
        if not clean:
            return []
        data = await self.safe_get(
            "/coins/markets",
            params={
                "vs_currency": "usd",
                "ids": ",".join(clean),
                "price_change_percentage": "1h,24h,7d,30d,90d,1y",
                "sparkline": "false",
            },
        )
        return data if isinstance(data, list) else []

    async def get_historical_market_chart(self, id: str) -> dict[str, Any]:  # noqa: A002 - CoinGecko API uses id
        clean = id.strip().lower()
        if not clean:
            return {}
        data = await self.safe_get(f"/coins/{clean}/market_chart", params={"vs_currency": "usd", "days": "90"})
        return data if isinstance(data, dict) else {}

    async def get_top_coins(self) -> list[dict[str, Any]]:
        data = await self.safe_get(
            "/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 100,
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "1h,24h,7d,30d,90d,1y",
            },
        )
        return data if isinstance(data, list) else []


class CoinGeckoProvider:
    """Synchronous CoinGecko market provider for crypto assets.

    This provider is intentionally side-effect free: it does not persist data,
    create tasks or expose endpoints. It only fetches and normalizes market
    payloads for upper layers.
    """

    base_url = "https://api.coingecko.com/api/v3/coins/markets"

    def __init__(self, *, timeout: float = 15.0) -> None:
        self.timeout = timeout

    @staticmethod
    def _clean_id(coin_id: str) -> str:
        return str(coin_id or "").strip().lower()

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError, CoinGeckoRateLimitError, CoinGeckoServerError)),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _fetch_markets_payload(self, ids: list[str], vs_currency: str) -> list[dict[str, Any]]:
        params = {
            "vs_currency": vs_currency,
            "ids": ",".join(ids),
            "price_change_percentage": "24h,7d,30d",
        }
        logger.info("CoinGecko markets request started", extra={"ids": ids, "vs_currency": vs_currency})

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.base_url, params=params)
        except httpx.TimeoutException:
            logger.warning("CoinGecko markets request timed out", extra={"ids": ids})
            raise
        except httpx.TransportError as exc:
            logger.warning("CoinGecko markets transport error", extra={"ids": ids, "error": str(exc)})
            raise

        if response.status_code == 429:
            logger.warning("CoinGecko rate limit reached", extra={"ids": ids, "status_code": response.status_code})
            raise CoinGeckoRateLimitError("CoinGecko rate limit reached")
        if response.status_code >= 500:
            logger.warning("CoinGecko markets server error", extra={"ids": ids, "status_code": response.status_code})
            raise CoinGeckoServerError(f"CoinGecko HTTP {response.status_code}")
        if response.status_code >= 400:
            logger.warning("CoinGecko markets HTTP error", extra={"ids": ids, "status_code": response.status_code})
            return []

        try:
            payload = response.json()
        except ValueError as exc:
            logger.error("CoinGecko returned invalid JSON", extra={"ids": ids, "error": str(exc)})
            return []

        if not isinstance(payload, list):
            logger.warning("CoinGecko returned non-list payload", extra={"ids": ids, "payload_type": type(payload).__name__})
            return []
        return [item for item in payload if isinstance(item, dict)]


    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError, CoinGeckoRateLimitError, CoinGeckoServerError)),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _fetch_markets_page_payload(
        self,
        *,
        vs_currency: str,
        per_page: int,
        page: int,
    ) -> list[dict[str, Any]]:
        safe_per_page = min(max(int(per_page or 250), 1), 250)
        safe_page = max(int(page or 1), 1)
        params = {
            "vs_currency": vs_currency,
            "order": "market_cap_desc",
            "per_page": safe_per_page,
            "page": safe_page,
            "sparkline": "false",
            "price_change_percentage": "24h,7d,30d",
        }
        logger.debug(
            "CoinGecko markets page request started",
            extra={"vs_currency": vs_currency, "per_page": safe_per_page, "page": safe_page},
        )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.base_url, params=params)
        except httpx.TimeoutException:
            logger.warning("CoinGecko markets page timed out", extra={"page": safe_page})
            raise
        except httpx.TransportError as exc:
            logger.warning("CoinGecko markets page transport error", extra={"page": safe_page, "error": str(exc)})
            raise

        if response.status_code == 429:
            logger.warning("CoinGecko page rate limit reached", extra={"page": safe_page, "status_code": response.status_code})
            raise CoinGeckoRateLimitError("CoinGecko rate limit reached")
        if response.status_code >= 500:
            logger.warning("CoinGecko markets page server error", extra={"page": safe_page, "status_code": response.status_code})
            raise CoinGeckoServerError(f"CoinGecko HTTP {response.status_code}")
        if response.status_code >= 400:
            logger.warning("CoinGecko markets page HTTP error", extra={"page": safe_page, "status_code": response.status_code})
            raise CoinGeckoProviderError(f"CoinGecko HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            logger.error("CoinGecko page returned invalid JSON", extra={"page": safe_page, "error": str(exc)})
            return []

        if not isinstance(payload, list):
            logger.warning(
                "CoinGecko page returned non-list payload",
                extra={"page": safe_page, "payload_type": type(payload).__name__},
            )
            return []
        logger.debug("CoinGecko markets page request finished", extra={"page": safe_page, "returned": len(payload)})
        return [item for item in payload if isinstance(item, dict)]

    def fetch_markets_by_pages(
        self,
        vs_currency: str = "brl",
        per_page: int = 250,
        pages: int = 4,
    ) -> list[dict[str, Any]]:
        """Fetch a broad CoinGecko catalog using /coins/markets pagination.

        The method is fail-soft by page: one broken page is logged and stored in
        ``last_page_errors`` but does not discard already fetched pages.
        """
        safe_pages = max(int(pages or 4), 1)
        safe_per_page = min(max(int(per_page or 250), 1), 250)
        self.last_page_errors: list[dict[str, Any]] = []
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()

        for page in range(1, safe_pages + 1):
            try:
                payload = self._fetch_markets_page_payload(
                    vs_currency=vs_currency,
                    per_page=safe_per_page,
                    page=page,
                )
            except Exception as exc:  # noqa: BLE001 - keep mass sync resilient
                self.last_page_errors.append({"page": page, "error": str(exc)})
                logger.error("CoinGecko markets page failed", extra={"page": page, "error": str(exc)})
                continue

            for item in payload:
                market = self._normalize_market(item)
                if market is None:
                    logger.warning("CoinGecko market ignored during page normalization", extra={"page": page, "payload": item})
                    continue
                coin_id = market["id"]
                if coin_id in seen:
                    continue
                seen.add(coin_id)
                normalized.append(market)

        logger.info(
            "CoinGecko fetch_markets_by_pages finished",
            extra={
                "vs_currency": vs_currency,
                "pages": safe_pages,
                "per_page": safe_per_page,
                "returned": len(normalized),
                "page_errors": len(self.last_page_errors),
            },
        )
        return normalized

    def fetch_markets(self, ids: list[str], vs_currency: str = "brl") -> list[dict[str, Any]]:
        clean_ids: list[str] = []
        seen: set[str] = set()
        for coin_id in ids or []:
            normalized_id = self._clean_id(coin_id)
            if not normalized_id or normalized_id in seen:
                continue
            seen.add(normalized_id)
            clean_ids.append(normalized_id)

        if not clean_ids:
            logger.info("CoinGecko fetch_markets called without ids")
            return []

        try:
            payload = self._fetch_markets_payload(clean_ids, vs_currency)
        except Exception as exc:  # noqa: BLE001 - provider must fail closed
            logger.error("CoinGecko markets request failed", extra={"ids": clean_ids, "error": str(exc)})
            return []

        normalized: list[dict[str, Any]] = []
        if not payload:
            logger.warning("CoinGecko markets returned empty payload", extra={"ids": clean_ids})
            return []

        for item in payload:
            market = self._normalize_market(item)
            if market is None:
                logger.warning("CoinGecko market ignored during normalization", extra={"payload": item})
                continue
            normalized.append(market)

        logger.info("CoinGecko fetch_markets finished", extra={"requested": len(clean_ids), "returned": len(normalized)})
        return normalized

    def _normalize_market(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not payload:
            return None

        coin_id = str(payload.get("id") or "").strip().lower()
        symbol = str(payload.get("symbol") or "").strip().upper()
        price = _float_or_none(payload.get("current_price"))

        if not coin_id or not symbol or price is None:
            return None

        return {
            "id": coin_id,
            "symbol": symbol,
            "name": payload.get("name"),
            "price": price,
            "market_cap": _int_or_none(payload.get("market_cap")),
            "volume_24h": _int_or_none(payload.get("total_volume")),
            "change_24h": _float_or_none(payload.get("price_change_percentage_24h_in_currency")),
            "change_7d": _float_or_none(payload.get("price_change_percentage_7d_in_currency")),
            "change_30d": _float_or_none(payload.get("price_change_percentage_30d_in_currency")),
            "updated_at": datetime.utcnow(),
            "source": "COINGECKO",
        }


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
