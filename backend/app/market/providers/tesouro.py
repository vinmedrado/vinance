from __future__ import annotations

import asyncio
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_UP
from io import StringIO
import re
from typing import Any
import unicodedata

import httpx

from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class TesouroDiretoProvider:
    """Read the official daily Tesouro Transparente price/rate dataset."""

    source = "tesouro_transparente"
    url = (
        "https://www.tesourotransparente.gov.br/ckan/dataset/"
        "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
        "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/"
        "precotaxatesourodireto.csv"
    )

    def __init__(self, timeout: float = 30.0, retries: int = 2) -> None:
        self.timeout = timeout
        self.retries = retries

    async def fetch_produtos(self) -> list[dict[str, Any]]:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(self.url)
                    response.raise_for_status()
                rows = self.parse_csv(
                    response.content.decode("utf-8-sig"),
                    observed_at=datetime.now(timezone.utc),
                )
                if not rows:
                    raise TesouroProviderError(
                        "official Tesouro dataset has no valid latest-market rows"
                    )
                return rows
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Tesouro provider failed",
                    extra={"attempt": attempt + 1, "error_type": type(exc).__name__},
                )
                if attempt >= self.retries:
                    break
                await asyncio.sleep(0.5 * (attempt + 1))
        raise TesouroProviderError("official Tesouro dataset is unavailable") from last_error

    def parse_csv(
        self,
        content: str,
        *,
        observed_at: datetime,
    ) -> list[dict[str, Any]]:
        """Normalize only the most recent market date from the official CSV."""

        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        reader = csv.DictReader(StringIO(content), delimiter=";")
        required = {
            "Tipo Titulo",
            "Data Vencimento",
            "Data Base",
            "Taxa Compra Manha",
            "Taxa Venda Manha",
            "PU Compra Manha",
            "PU Venda Manha",
            "PU Base Manha",
        }
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise TesouroProviderError("official Tesouro CSV contract is not recognized")

        latest_date: date | None = None
        latest_rows: list[dict[str, str]] = []
        for row in reader:
            market_date = _date_or_none(row.get("Data Base"))
            if market_date is None:
                continue
            if latest_date is None or market_date > latest_date:
                latest_date = market_date
                latest_rows = [row]
            elif market_date == latest_date:
                latest_rows.append(row)

        normalized: list[dict[str, Any]] = []
        for row in latest_rows:
            source_name = str(row.get("Tipo Titulo") or "").strip()
            maturity = _date_or_none(row.get("Data Vencimento"))
            if not source_name or maturity is None or latest_date is None:
                raise TesouroProviderError(
                    "official Tesouro latest snapshot contains an invalid identity"
                )
            subtype, indexer, rate_type = _classify_product(source_name)
            source_product_id = f"{_slug(source_name)}:{maturity.isoformat()}"
            purchase_price = _decimal_or_none(row.get("PU Compra Manha"))
            redemption_price = _decimal_or_none(row.get("PU Venda Manha"))
            base_price = _decimal_or_none(row.get("PU Base Manha"))
            minimum = (
                (purchase_price * Decimal("0.01")).quantize(
                    Decimal("0.01"), rounding=ROUND_UP
                )
                if purchase_price is not None and purchase_price > 0
                else None
            )
            normalized.append(
                {
                    "source_product_id": source_product_id,
                    "asset_catalog_id": None,
                    "nome": f"{source_name} {maturity.year}",
                    "emissor": "Tesouro Nacional",
                    "tipo": subtype,
                    "indexador": indexer,
                    "taxa_juros": _decimal_or_none(row.get("Taxa Compra Manha")),
                    "taxa_total_equiv": _decimal_or_none(row.get("Taxa Venda Manha")),
                    "rate_type": rate_type,
                    "purchase_rate": _decimal_or_none(row.get("Taxa Compra Manha")),
                    "redemption_rate": _decimal_or_none(row.get("Taxa Venda Manha")),
                    "unit_price": purchase_price,
                    "redemption_unit_price": redemption_price,
                    "base_unit_price": base_price,
                    "vencimento": maturity,
                    # The source proves daily repurchase, but does not expose a
                    # universal settlement-day value in this dataset.
                    "liquidez_dias": None,
                    "liquidity_type": "DAILY_REPURCHASE",
                    "investimento_minimo": minimum,
                    "garantia_fgc": False,
                    "guarantee_type": "SOVEREIGN_ISSUER",
                    "tax_treatment": None,
                    "codigo_tesouro": source_product_id,
                    "selic_vigente": None,
                    "ipca_12m": None,
                    "currency": "BRL",
                    "market_date": latest_date,
                    "source_metadata": {
                        "official_title": source_name,
                        "dataset": "taxas-dos-titulos-ofertados-pelo-tesouro-direto",
                    },
                    "source": self.source,
                    "coletado_em": observed_at,
                    "is_active": True,
                }
            )
        return sorted(normalized, key=lambda item: item["source_product_id"])


class TesouroProviderError(RuntimeError):
    pass


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        text = str(value).strip()
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _date_or_none(value: Any) -> date | None:
    if not value:
        return None
    text = str(value)[:10]
    try:
        if "/" in str(value):
            text = str(value).strip()
            day, month, year = text.split("/")
            return datetime(int(year), int(month), int(day)).date()
        return datetime.fromisoformat(text).date()
    except (TypeError, ValueError):
        return None


def _slug(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")


def _classify_product(name: str) -> tuple[str, str, str]:
    upper = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().upper()
    if "RENDA+" in upper or "RENDA +" in upper:
        return "TREASURY_RENDA_PLUS", "IPCA", "INFLATION_LINKED_SPREAD"
    if "EDUCA+" in upper or "EDUCA +" in upper:
        return "TREASURY_EDUCA_PLUS", "IPCA", "INFLATION_LINKED_SPREAD"
    if "SELIC" in upper:
        return "TREASURY_SELIC", "SELIC", "FLOATING_SPREAD"
    if "IPCA" in upper:
        return "TREASURY_IPCA", "IPCA", "INFLATION_LINKED_SPREAD"
    if "PREFIXADO" in upper:
        return "TREASURY_PREFIXED", "PREFIXED", "FIXED"
    return "TREASURY_OTHER", "OTHER", "OTHER"
