from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class StatusInvestProviderError(RuntimeError):
    """Controlled Status Invest provider error."""


class StatusInvestRateLimitError(StatusInvestProviderError):
    """Raised when Status Invest responds with HTTP 429."""


class StatusInvestForbiddenError(StatusInvestProviderError):
    """Raised when Status Invest responds with HTTP 403."""


class StatusInvestClient:
    """JSON-first async client for Status Invest fundamentals.

    The client is intentionally conservative: no fixed cookies, no proxy, no
    browser automation and no anti-bot bypass. HTML is exposed only as a light
    fallback for asset detail pages and parsing/persistence are owned by the
    service layer.
    """

    base_url = "https://statusinvest.com.br"
    advanced_search_path = "/category/advancedsearchresult"
    acoes_referer = "https://statusinvest.com.br/acoes/busca-avancada"
    fiis_referer = "https://statusinvest.com.br/fundos-imobiliarios/busca-avancada"
    acoes_category_type = 1
    fiis_category_type = 2

    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        max_concurrency: int = 2,
        min_interval_seconds: float = 0.8,
        cooldown_429_seconds: float = 8.0,
    ) -> None:
        self.timeout = httpx.Timeout(timeout_seconds)
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._min_interval_seconds = max(0.0, min_interval_seconds)
        self._cooldown_429_seconds = max(0.0, cooldown_429_seconds)
        self._persistent_403_count = 0

    @staticmethod
    def _headers(*, referer: str, accept_json: bool = True) -> dict[str, str]:
        accept = "application/json, text/plain, */*" if accept_json else "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": accept,
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": referer,
            "Origin": StatusInvestClient.base_url,
            "Connection": "keep-alive",
        }

    @staticmethod
    def _range_filter(min_value: float | int | None = None, max_value: float | int | None = None) -> dict[str, float | int | None]:
        return {"Item1": min_value, "Item2": max_value}

    @classmethod
    def build_acoes_search_payload(cls) -> dict[str, Any]:
        rf = cls._range_filter
        return {
            "Sector": "",
            "SubSector": "",
            "Segment": "",
            "my_range": "-20;100",
            "dy": rf(),
            "p_L": rf(),
            "peg_Ratio": rf(),
            "p_VP": rf(),
            "p_Ativo": rf(),
            "margemBruta": rf(),
            "margemEbit": rf(),
            "margemLiquida": rf(),
            "p_Ebit": rf(),
            "eV_Ebit": rf(),
            "eV_Ebitda": rf(),
            "dividaLiquidaEbit": rf(),
            "dividaLiquidaEbitda": rf(),
            "dividaLiquidaPatrimonioLiquido": rf(),
            "p_SR": rf(),
            "roe": rf(),
            "roic": rf(),
            "roa": rf(),
            "liquidezMediaDiaria": rf(),
            "valorMercado": rf(),
        }

    @classmethod
    def build_fiis_search_payload(cls) -> dict[str, Any]:
        rf = cls._range_filter
        return {
            "Segment": "",
            "my_range": "-20;100",
            "dy": rf(),
            "p_VP": rf(),
            "valorPatrimonial": rf(),
            "patrimonioLiquido": rf(),
            "liquidezMediaDiaria": rf(),
            "vpa": rf(),
        }

    async def _sleep_before_request(self) -> None:
        if self._min_interval_seconds:
            await asyncio.sleep(self._min_interval_seconds)

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError, StatusInvestRateLimitError)),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        referer: str,
        accept_json: bool = True,
    ) -> httpx.Response:
        async with self._semaphore:
            if self._persistent_403_count >= 3:
                raise StatusInvestForbiddenError("Status Invest returned persistent 403; circuit breaker opened")
            await self._sleep_before_request()
            url = f"{self.base_url}{path}"
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=self._headers(referer=referer, accept_json=accept_json)) as client:
                response = await client.request(method, url, params=params)
            if response.status_code == 429:
                logger.warning("Status Invest rate limit reached", extra={"path": path, "status_code": response.status_code})
                if self._cooldown_429_seconds:
                    await asyncio.sleep(self._cooldown_429_seconds)
                raise StatusInvestRateLimitError("Status Invest rate limit reached")
            if response.status_code == 403:
                self._persistent_403_count += 1
                logger.warning("Status Invest forbidden response", extra={"path": path, "count": self._persistent_403_count})
                raise StatusInvestForbiddenError("Status Invest returned 403")
            response.raise_for_status()
            self._persistent_403_count = 0
            return response

    async def safe_json_request(self, *, params: Mapping[str, Any], category_type: int, referer: str) -> dict[str, Any]:
        try:
            response = await self._request("GET", self.advanced_search_path, params={"search": _compact_payload(params), "CategoryType": category_type}, referer=referer)
            content_type = response.headers.get("content-type", "")
            text_preview = response.text[:120] if response.text else ""
            if "html" in content_type.lower() or text_preview.lstrip().startswith("<"):
                logger.warning(
                    "Status Invest advanced search returned HTML instead of JSON",
                    extra={"category_type": category_type, "content_type": content_type, "preview": text_preview[:80]},
                )
                return {"data": [], "_meta": {"content_type": content_type, "response_kind": "html"}}
            try:
                payload = response.json()
            except ValueError:
                logger.warning(
                    "Status Invest advanced search returned non-JSON response",
                    extra={"category_type": category_type, "content_type": content_type, "preview": text_preview[:80]},
                )
                return {"data": [], "_meta": {"content_type": content_type, "response_kind": "non_json"}}
            meta = {"content_type": content_type, "response_kind": type(payload).__name__}
            if isinstance(payload, dict):
                payload.setdefault("_meta", meta)
                logger.info(
                    "Status Invest JSON payload received",
                    extra={"category_type": category_type, "content_type": content_type, "keys": list(payload.keys())[:20]},
                )
                return payload
            if isinstance(payload, list):
                logger.info(
                    "Status Invest JSON list received",
                    extra={"category_type": category_type, "content_type": content_type, "rows": len(payload)},
                )
                return {"data": payload, "_meta": meta}
            return {"data": [], "warning": "unexpected_json_type", "_meta": meta}
        except Exception as exc:  # noqa: BLE001 - provider failures must be controlled
            logger.warning("Status Invest JSON request failed", extra={"category_type": category_type, "error": str(exc)})
            return {"data": [], "error": str(exc)}

    async def get_advanced_search(self, *, payload: Mapping[str, Any], category_type: int, referer: str) -> dict[str, Any]:
        return await self.safe_json_request(params=payload, category_type=category_type, referer=referer)

    async def get_acoes_batch(self, tickers: Sequence[str] | None = None) -> dict[str, Any]:
        payload = self.build_acoes_search_payload()
        # The Status Invest advanced search is broad; ticker filtering is done in service after payload normalization.
        _ = tickers
        return await self.get_advanced_search(payload=payload, category_type=self.acoes_category_type, referer=self.acoes_referer)

    async def get_fiis_batch(self, tickers: Sequence[str] | None = None) -> dict[str, Any]:
        payload = self.build_fiis_search_payload()
        _ = tickers
        return await self.get_advanced_search(payload=payload, category_type=self.fiis_category_type, referer=self.fiis_referer)

    async def get_asset_page(self, *, ticker: str, market: str) -> str | None:
        clean_ticker = ticker.strip().lower()
        clean_market = market.strip().lower()
        if not clean_ticker or clean_market not in {"acoes", "fii"}:
            return None
        path_prefix = "acoes" if clean_market == "acoes" else "fundos-imobiliarios"
        referer = self.acoes_referer if clean_market == "acoes" else self.fiis_referer
        try:
            response = await self._request("GET", f"/{path_prefix}/{clean_ticker}", referer=referer, accept_json=False)
            return response.text
        except Exception as exc:  # noqa: BLE001
            logger.info("Status Invest HTML fallback unavailable", extra={"ticker": ticker, "market": market, "error": str(exc)})
            return None


def _compact_payload(value: Mapping[str, Any]) -> str:
    import json

    return json.dumps(dict(value), ensure_ascii=False, separators=(",", ":"))
