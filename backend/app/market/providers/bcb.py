from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Any

import httpx

from backend.app.core.logging import get_logger

logger = get_logger(__name__)

BCB_CODES = {
    "SELIC": {"series": 432, "name": "Taxa Selic Meta"},
    "IPCA": {"series": 433, "name": "IPCA mensal"},
    "CDI": {"series": 12, "name": "CDI diário"},
}


class BCBProvider:
    source = "bcb"

    def __init__(self, timeout: float = 10.0, retries: int = 2) -> None:
        self.timeout = timeout
        self.retries = retries

    async def fetch_indicator(self, code: str, *, last: int = 1) -> list[dict[str, Any]]:
        normalized = code.strip().upper()
        metadata = BCB_CODES[normalized]
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{metadata['series']}/dados/ultimos/{last}?formato=json"
        for attempt in range(self.retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    rows = response.json()
                return [
                    {
                        "code": normalized,
                        "name": metadata["name"],
                        "date": _parse_brazilian_date(row["data"]),
                        "value": Decimal(str(row["valor"]).replace(",", ".")),
                        "source": self.source,
                    }
                    for row in rows
                ]
            except Exception as exc:  # provider failure must not break the app
                logger.warning("BCB provider failed", extra={"code": normalized, "attempt": attempt + 1, "error": str(exc)})
                if attempt >= self.retries:
                    return []
                await asyncio.sleep(0.5 * (attempt + 1))
        return []

    async def fetch_initial_indicators(self) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for code in BCB_CODES:
            payloads.extend(await self.fetch_indicator(code, last=1))
        return payloads


def _parse_brazilian_date(value: str) -> date:
    day, month, year = value.split("/")
    return date(int(year), int(month), int(day))
