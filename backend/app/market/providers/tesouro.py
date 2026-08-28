from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class TesouroDiretoProvider:
    source = "tesouro_direto"
    url = "https://www.tesourodireto.com.br/json/br/com/b3/tesourodireto/service/api/treasurybondsinfo.json"

    def __init__(self, timeout: float = 10.0, retries: int = 2) -> None:
        self.timeout = timeout
        self.retries = retries

    async def fetch_produtos(self) -> list[dict[str, Any]]:
        for attempt in range(self.retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(self.url)
                    response.raise_for_status()
                    payload = response.json()
                return self._normalize(payload)
            except Exception as exc:
                logger.warning("Tesouro provider failed", extra={"attempt": attempt + 1, "error": str(exc)})
                if attempt >= self.retries:
                    return []
                await asyncio.sleep(0.5 * (attempt + 1))
        return []

    def _normalize(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows = payload.get("response", {}).get("TrsrBdTradgList", [])
        now = datetime.now(timezone.utc)
        normalized: list[dict[str, Any]] = []
        for row in rows:
            bond = row.get("TrsrBd", {})
            name = str(bond.get("nm", "")).strip()
            if not name:
                continue
            normalized.append(
                {
                    "nome": name,
                    "emissor": "Tesouro Nacional",
                    "tipo": "tesouro_direto",
                    "indexador": bond.get("FinIndxs", {}).get("nm") if isinstance(bond.get("FinIndxs"), dict) else None,
                    "taxa_juros": _decimal_or_none(bond.get("anulInvstmtRate")),
                    "taxa_total_equiv": _decimal_or_none(bond.get("anulRedRate")),
                    "vencimento": _date_or_none(bond.get("mtrtyDt")),
                    "liquidez_dias": 1,
                    "investimento_minimo": _decimal_or_none(bond.get("minInvstmtAmt")),
                    "garantia_fgc": False,
                    "codigo_tesouro": str(bond.get("cd", "")).strip() or None,
                    "selic_vigente": None,
                    "ipca_12m": None,
                    "source": self.source,
                    "coletado_em": now,
                    "is_active": True,
                }
            )
        return normalized


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except Exception:
        return None


def _date_or_none(value: Any):
    if not value:
        return None
    text = str(value)[:10]
    try:
        if "/" in text:
            day, month, year = text.split("/")
            return datetime(int(year), int(month), int(day)).date()
        return datetime.fromisoformat(text).date()
    except Exception:
        return None
