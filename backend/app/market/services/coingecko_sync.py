from __future__ import annotations

import logging
import time
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

try:  # keep unit-test imports lightweight in minimal environments
        from sqlalchemy.ext.asyncio import AsyncSession
except Exception:  # pragma: no cover
    select = None  # type: ignore[assignment]
    AsyncSession = Any  # type: ignore[misc,assignment]

from backend.app.market.providers.coingecko import CoinGeckoProvider

try:
    from backend.app.market.models.cripto import CriptoFundamental
    from backend.app.market.models.sync_log import SyncLog
except Exception:  # pragma: no cover
    CriptoFundamental = SyncLog = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

SOURCE = "COINGECKO"
MERCADO = "CRIPTO"


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        logger.warning("coingecko_sync.invalid_decimal", extra={"value": value})
        return None


def _to_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    raw = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    logger.warning("coingecko_sync.invalid_date", extra={"value": value})
    return None


class CoinGeckoSyncService:
    """Persist normalized CoinGecko market data into cripto_fundamentals.

    Cripto é mercado 24/7; cada coleta do CoinGecko deve gerar uma nova
    linha intraday. Portanto, este serviço faz insert append-only para
    fundamentos cripto e mantém upsert apenas para mercados diários em
    outros serviços.
    """

    def __init__(self, provider: CoinGeckoProvider | None = None) -> None:
        self.provider = provider or CoinGeckoProvider()

    async def sync_markets(
        self,
        session: AsyncSession,
        ids: list[str],
        vs_currency: str = "brl",
    ) -> dict:
        run_id = uuid.uuid4().hex
        started_at = datetime.utcnow()
        start_perf = time.perf_counter()
        clean_ids = self._clean_ids(ids)

        if not clean_ids:
            summary = self._summary(run_id, "SUCCESS", 0, 0, 0, 0.0, 0.0)
            await self._write_sync_log(session, summary, started_at, datetime.utcnow())
            await session.commit()
            return summary

        try:
            results = self.provider.fetch_markets(clean_ids, vs_currency=vs_currency)
            ok = 0
            errors = 0

            for payload in results:
                try:
                    await self._insert_payload(session, payload, vs_currency=vs_currency)
                    ok += 1
                except Exception as exc:  # noqa: BLE001 - one bad coin must not break all sync
                    errors += 1
                    logger.error(
                        "coingecko_sync.asset_failed",
                        extra={"coin_id": payload.get("id"), "error": str(exc)},
                    )

            total = len(clean_ids)
            missing = max(total - len(results), 0)
            errors += missing
            sucesso_pct = (ok / max(total, 1)) * 100
            tempo_segundos = time.perf_counter() - start_perf
            status = "SUCCESS" if errors == 0 else "PARTIAL_SUCCESS"

            summary = self._summary(run_id, status, total, ok, errors, sucesso_pct, tempo_segundos)
            await self._write_sync_log(session, summary, started_at, datetime.utcnow())
            await session.commit()
            logger.info("coingecko_sync.completed", extra=summary)
            return summary

        except Exception as exc:  # provider/general failure
            await session.rollback()
            tempo_segundos = time.perf_counter() - start_perf
            summary = self._summary(run_id, "FAILED", len(clean_ids), 0, len(clean_ids), 0.0, tempo_segundos)
            summary["error_message"] = str(exc)
            try:
                await self._write_sync_log(session, summary, started_at, datetime.utcnow(), error_message=str(exc))
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("coingecko_sync.failed_to_write_sync_log")
            logger.error("coingecko_sync.failed", extra={"run_id": run_id, "error": str(exc)})
            return summary

    async def sync_markets_by_pages(
        self,
        session: AsyncSession,
        vs_currency: str = "brl",
        per_page: int = 250,
        pages: int = 4,
    ) -> dict:
        run_id = uuid.uuid4().hex
        started_at = datetime.utcnow()
        start_perf = time.perf_counter()

        safe_per_page = min(max(int(per_page or 250), 1), 250)
        safe_pages = max(int(pages or 4), 1)

        try:
            results = self.provider.fetch_markets_by_pages(
                vs_currency=vs_currency,
                per_page=safe_per_page,
                pages=safe_pages,
            )
            page_errors = list(getattr(self.provider, "last_page_errors", []) or [])
            ok = 0
            errors = len(page_errors)

            for payload in results:
                try:
                    await self._insert_payload(session, payload, vs_currency=vs_currency)
                    ok += 1
                except Exception as exc:  # noqa: BLE001 - one bad coin must not break all sync
                    errors += 1
                    logger.error(
                        "coingecko_sync.asset_failed",
                        extra={"coin_id": payload.get("id"), "error": str(exc)},
                    )

            total = ok + errors
            sucesso_pct = (ok / max(total, 1)) * 100
            tempo_segundos = time.perf_counter() - start_perf
            if errors == 0:
                status = "SUCCESS"
            elif ok > 0:
                status = "PARTIAL_SUCCESS"
            else:
                status = "FAILED"

            summary = self._summary(run_id, status, total, ok, errors, sucesso_pct, tempo_segundos)
            summary["pages"] = safe_pages
            summary["per_page"] = safe_per_page
            summary["page_errors"] = page_errors
            await self._write_sync_log(session, summary, started_at, datetime.utcnow())
            await session.commit()
            logger.info("coingecko_sync.pages_completed", extra=summary)
            return summary

        except Exception as exc:  # provider/general failure
            await session.rollback()
            tempo_segundos = time.perf_counter() - start_perf
            summary = self._summary(run_id, "FAILED", 0, 0, 1, 0.0, tempo_segundos)
            summary["pages"] = safe_pages
            summary["per_page"] = safe_per_page
            summary["error_message"] = str(exc)
            try:
                await self._write_sync_log(session, summary, started_at, datetime.utcnow(), error_message=str(exc))
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("coingecko_sync.failed_to_write_sync_log")
            logger.error("coingecko_sync.pages_failed", extra={"run_id": run_id, "error": str(exc)})
            return summary

    @staticmethod
    def _clean_ids(ids: list[str]) -> list[str]:
        clean: list[str] = []
        seen: set[str] = set()
        for coin_id in ids or []:
            normalized = str(coin_id or "").strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            clean.append(normalized)
        return clean

    def _summary(
        self,
        run_id: str,
        status: str,
        total: int,
        ok: int,
        erros: int,
        sucesso_pct: float,
        tempo_segundos: float,
    ) -> dict:
        return {
            "run_id": run_id,
            "source": SOURCE,
            "mercado": MERCADO,
            "status": status,
            "total": total,
            "ok": ok,
            "erros": erros,
            "sucesso_pct": sucesso_pct,
            "tempo_segundos": tempo_segundos,
        }

    async def _write_sync_log(
        self,
        session: AsyncSession,
        summary: dict,
        started_at: datetime,
        finished_at: datetime,
        error_message: str | None = None,
    ) -> None:
        if SyncLog is None:
            logger.warning("coingecko_sync.sync_log_model_unavailable")
            return
        session.add(SyncLog(
            run_id=summary["run_id"],
            source=summary["source"],
            mercado=summary["mercado"],
            status=summary["status"],
            total=summary["total"],
            ok=summary["ok"],
            erros=summary["erros"],
            sucesso_pct=summary["sucesso_pct"],
            tempo_segundos=summary["tempo_segundos"],
            started_at=started_at,
            finished_at=finished_at,
            error_message=error_message or summary.get("error_message"),
        ))

    async def _insert_payload(self, session: AsyncSession, payload: dict, vs_currency: str = "brl") -> None:
        """Insert one intraday crypto snapshot without daily de-duplication."""
        if CriptoFundamental is None:
            raise RuntimeError("Model CriptoFundamental indisponível")

        values = self._map_payload(payload, vs_currency=vs_currency)
        values = self._filter_model_fields(CriptoFundamental, values)
        session.add(CriptoFundamental(**values))

    async def _upsert_payload(self, session: AsyncSession, payload: dict, vs_currency: str = "brl") -> None:
        """Backward-compatible alias; crypto persistence is append-only."""
        await self._insert_payload(session, payload, vs_currency=vs_currency)

    def _map_payload(self, payload: dict, vs_currency: str = "brl") -> dict:
        coin_id = str(payload.get("id") or payload.get("coin_id") or "").strip().lower()
        ticker = str(payload.get("symbol") or payload.get("ticker") or "").strip().upper()
        if not coin_id:
            raise ValueError("Payload sem id")
        if not ticker:
            raise ValueError("Payload sem symbol/ticker")

        # Preserve the ingestion timestamp. CoinGecko may send an asset
        # last-updated timestamp, but historical intraday rows need the actual
        # collection time so repeated syncs in the same day do not collapse.
        coletado_em = payload.get("coletado_em") or datetime.utcnow()
        if not isinstance(coletado_em, datetime):
            coletado_em = datetime.utcnow()

        currency = str(vs_currency or "brl").strip().lower()
        price_column = "price_brl" if currency == "brl" else "price_usd"

        values = {
            "coin_id": coin_id,
            "ticker": ticker,
            "name": payload.get("name") or ticker,
            "date": _to_date(payload.get("date")) or datetime.utcnow().date(),
            price_column: _to_decimal(payload.get("price")),
            "market_cap_usd": _to_decimal(payload.get("market_cap")),
            "volume_24h_usd": _to_decimal(payload.get("volume_24h")),
            "price_change_24h_pct": _to_decimal(payload.get("change_24h")),
            "price_change_7d_pct": _to_decimal(payload.get("change_7d")),
            "price_change_30d_pct": _to_decimal(payload.get("change_30d")),
            "source": payload.get("source") or SOURCE,
            "coletado_em": coletado_em,
        }
        return values

    def _filter_model_fields(self, model: Any, values: dict) -> dict:
        columns = set(getattr(getattr(model, "__table__", None), "columns", {}).keys())
        if not columns:
            return values

        filtered = {}
        for key, value in values.items():
            if key in columns:
                filtered[key] = value
            else:
                logger.warning(
                    "coingecko_sync.ignored_missing_model_field",
                    extra={"model": getattr(model, "__name__", str(model)), "field": key},
                )
        return filtered
