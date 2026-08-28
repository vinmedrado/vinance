from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from collections import Counter
from datetime import timezone
from typing import Any

try:  # keeps lightweight unit tests importable in environments without backend deps installed
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
except Exception:  # pragma: no cover
    select = None  # type: ignore[assignment]
    AsyncSession = Any  # type: ignore[misc,assignment]

from backend.app.market.providers.investidor10 import Investidor10Provider

try:
    from backend.app.market.models.acoes import AcaoFundamental
    from backend.app.market.models.bdr import BdrFundamental
    from backend.app.market.models.etf import EtfFundamental
    from backend.app.market.models.fii import FiiFundamental
    from backend.app.market.models.sync_log import SyncLog
    from backend.app.market.models.sync_error_log import SyncErrorLog
except Exception:  # pragma: no cover
    AcaoFundamental = BdrFundamental = EtfFundamental = FiiFundamental = SyncLog = SyncErrorLog = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

SOURCE = "INVESTIDOR10"
VALID_MARKETS = {"FIIS", "ACOES", "ETF", "BDR"}
DEFAULT_WORKERS = 2
MAX_WORKERS = 4
DEFAULT_THROTTLE_SECONDS = 0.35

ERROR_TIMEOUT = "TIMEOUT"
ERROR_BLOQUEIO = "BLOQUEIO"
ERROR_HTTP = "HTTP_ERROR"
ERROR_PARSE = "PARSE_ERROR"
ERROR_UNKNOWN = "UNKNOWN"
RETRYABLE_ERRORS = {ERROR_TIMEOUT, ERROR_HTTP, ERROR_UNKNOWN}


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        logger.warning("investidor10_sync.invalid_decimal", extra={"value": value})
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
    logger.warning("investidor10_sync.invalid_date", extra={"value": value})
    return None


class Investidor10SyncService:
    def __init__(self, provider: Investidor10Provider | None = None) -> None:
        self.provider = provider or Investidor10Provider()

    def _sanitize_workers(self, workers: int | None) -> int:
        try:
            selected = int(workers or DEFAULT_WORKERS)
        except (TypeError, ValueError):
            selected = DEFAULT_WORKERS
        return max(1, min(selected, MAX_WORKERS))

    def _normalize_tickers(self, tickers: list[str] | None) -> list[str]:
        clean_tickers: list[str] = []
        seen: set[str] = set()
        for ticker in tickers or []:
            clean = str(ticker or "").strip().upper()
            if clean and clean not in seen:
                clean_tickers.append(clean)
                seen.add(clean)
        return clean_tickers

    @classmethod
    def classify_error(cls, error: Any) -> str:
        msg = str(error or "").lower()
        if "timeout" in msg or "timed out" in msg:
            return ERROR_TIMEOUT
        if "cloudflare" in msg or "bloqueado" in msg or "attention required" in msg or "proteção do site" in msg:
            return ERROR_BLOQUEIO
        if "http" in msg or "status" in msg or "429" in msg or "5xx" in msg or "connection" in msg or "remote disconnected" in msg:
            return ERROR_HTTP
        if "parse" in msg or "could not convert" in msg or "invalid literal" in msg or "payload sem ticker" in msg or "html inesperado" in msg:
            return ERROR_PARSE
        return ERROR_UNKNOWN

    @classmethod
    def should_retry(cls, error: Any) -> bool:
        msg = str(error or "").lower()
        tipo = cls.classify_error(msg)
        if "http 404" in msg or "http 410" in msg:
            return False
        if tipo in {ERROR_BLOQUEIO, ERROR_PARSE}:
            return False
        if "http 500" in msg or "http 502" in msg or "http 503" in msg or "http 504" in msg:
            return True
        if tipo in {ERROR_TIMEOUT, ERROR_HTTP} and ("connection" in msg or "timeout" in msg or "timed out" in msg):
            return True
        return False

    async def sync_market(
        self,
        session: AsyncSession,
        mercado: str,
        tickers: list[str],
        workers: int | None = None,
        throttle_seconds: float = DEFAULT_THROTTLE_SECONDS,
        cooldown_seconds: float | None = None,
        max_attempts: int = 2,
    ) -> dict:
        mercado = self._normalize_market(mercado)
        clean_tickers = self._normalize_tickers(tickers)
        selected_workers = self._sanitize_workers(workers)
        run_id = uuid.uuid4().hex
        started_at = datetime.utcnow()
        start_perf = time.perf_counter()

        logger.info(
            "investidor10_sync.started",
            extra={"run_id": run_id, "mercado": mercado, "ativos": len(clean_tickers), "workers": selected_workers},
        )

        if not clean_tickers:
            summary = self._summary(run_id, mercado, "SUCCESS", 0, 0, 0, 0.0, started_at, 0.0, selected_workers, {})
            await self._write_sync_log(session, summary, started_at, datetime.utcnow())
            await session.commit()
            return summary

        semaphore = asyncio.Semaphore(selected_workers)
        results: list[dict] = []
        errors: list[dict] = []
        errors_by_type: Counter[str] = Counter()

        async def run_one(index: int, ticker: str) -> None:
            async with semaphore:
                if throttle_seconds > 0 and index > 0:
                    await asyncio.sleep(throttle_seconds)
                item = await self._scrape_ticker_with_retry(mercado, ticker, max_attempts=max_attempts)
                if item["ok"]:
                    results.append(item["data"])
                else:
                    error_item = {
                        "run_id": run_id,
                        "mercado": mercado,
                        "ticker": ticker,
                        "tipo_erro": item["tipo_erro"],
                        "erro": item["erro"],
                        "segundos": round(float(item.get("segundos") or 0.0), 3),
                        "processado_em": datetime.utcnow(),
                    }
                    errors.append(error_item)
                    errors_by_type[error_item["tipo_erro"]] += 1
                    await self._write_error_log(session, error_item)
                    if cooldown_seconds and error_item["tipo_erro"] == ERROR_BLOQUEIO:
                        await asyncio.sleep(cooldown_seconds)
                processed = len(results) + len(errors)
                elapsed = time.perf_counter() - start_perf
                throughput = (processed / elapsed) * 60 if elapsed > 0 else 0.0
                logger.info(
                    "investidor10_sync.progress",
                    extra={"mercado": mercado, "processados": processed, "ok": len(results), "erros": len(errors), "throughput": round(throughput, 2)},
                )

        try:
            await asyncio.gather(*(run_one(index, ticker) for index, ticker in enumerate(clean_tickers)))
            for payload in results:
                await self._upsert_payload(session, mercado, payload)

            total = len(clean_tickers)
            ok = len(results)
            erros = len(errors)
            sucesso_pct = (ok / max(total, 1)) * 100
            tempo_segundos = time.perf_counter() - start_perf
            status = "SUCCESS" if erros == 0 else ("PARTIAL_SUCCESS" if ok > 0 else "FAILED")
            summary = self._summary(
                run_id,
                mercado,
                status,
                total,
                ok,
                erros,
                sucesso_pct,
                started_at,
                tempo_segundos,
                selected_workers,
                dict(errors_by_type),
            )
            await self._write_sync_log(session, summary, started_at, datetime.utcnow())
            await session.commit()
            logger.info("investidor10_sync.finished", extra=summary)
            return summary

        except Exception as exc:
            await session.rollback()
            tempo_segundos = time.perf_counter() - start_perf
            summary = self._summary(run_id, mercado, "FAILED", len(clean_tickers), len(results), len(clean_tickers) - len(results), 0.0, started_at, tempo_segundos, selected_workers, dict(errors_by_type))
            summary["error_message"] = str(exc)
            try:
                await self._write_sync_log(session, summary, started_at, datetime.utcnow(), error_message=str(exc))
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("investidor10_sync.failed_to_write_sync_log")
            logger.error("investidor10_sync.failed", extra={"mercado": mercado, "run_id": run_id, "error": str(exc)})
            return summary

    async def _scrape_ticker_with_retry(self, mercado: str, ticker: str, max_attempts: int) -> dict:
        attempts = max(1, int(max_attempts or 1))
        last_item: dict | None = None
        for attempt in range(1, attempts + 1):
            started = time.perf_counter()
            try:
                data = await asyncio.to_thread(self.provider._scrape_by_market, mercado, ticker)
                return {"ok": True, "mercado": mercado, "ticker": ticker, "segundos": time.perf_counter() - started, "data": data, "erro": None, "tipo_erro": None, "attempts": attempt}
            except Exception as exc:  # noqa: BLE001
                erro = str(exc)
                tipo = self.classify_error(erro)
                last_item = {"ok": False, "mercado": mercado, "ticker": ticker, "segundos": time.perf_counter() - started, "data": None, "erro": erro, "tipo_erro": tipo, "attempts": attempt}
                if attempt >= attempts or not self.should_retry(erro):
                    return last_item
                await asyncio.sleep(min(2 * attempt, 5))
        return last_item or {"ok": False, "mercado": mercado, "ticker": ticker, "segundos": 0.0, "data": None, "erro": "UNKNOWN", "tipo_erro": ERROR_UNKNOWN, "attempts": attempts}

    def _benchmark(self, total: int, ok: int, erros: int, tempo_segundos: float, errors_by_type: dict[str, int]) -> dict:
        ativos_por_minuto = (total / tempo_segundos) * 60 if tempo_segundos > 0 else 0.0
        return {
            "throughput": ativos_por_minuto,
            "ativos_por_minuto": ativos_por_minuto,
            "tempo_total": tempo_segundos,
            "sucesso_pct": (ok / max(total, 1)) * 100,
            "erros_pct": (erros / max(total, 1)) * 100,
            "bloqueios": int(errors_by_type.get(ERROR_BLOQUEIO, 0)),
            "timeouts": int(errors_by_type.get(ERROR_TIMEOUT, 0)),
        }

    def _summary(
        self,
        run_id: str,
        mercado: str,
        status: str,
        total: int,
        ok: int,
        erros: int,
        sucesso_pct: float,
        started_at: datetime,
        tempo_segundos: float = 0.0,
        workers: int = DEFAULT_WORKERS,
        errors_by_type: dict[str, int] | None = None,
    ) -> dict:
        errors_by_type = errors_by_type or {}
        benchmark = self._benchmark(total, ok, erros, tempo_segundos, errors_by_type)
        return {
            "run_id": run_id,
            "source": SOURCE,
            "mercado": mercado,
            "status": status,
            "total": total,
            "ok": ok,
            "erros": erros,
            "sucesso_pct": sucesso_pct,
            "erros_pct": benchmark["erros_pct"],
            "tempo_segundos": tempo_segundos,
            "tempo_total": benchmark["tempo_total"],
            "throughput": benchmark["throughput"],
            "ativos_por_minuto": benchmark["ativos_por_minuto"],
            "bloqueios": benchmark["bloqueios"],
            "timeouts": benchmark["timeouts"],
            "workers": workers,
            "errors_by_type": errors_by_type,
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
            logger.warning("investidor10_sync.sync_log_model_unavailable")
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

    async def _write_error_log(self, session: AsyncSession, error_item: dict) -> None:
        if SyncErrorLog is None:
            logger.warning("investidor10_sync.sync_error_log_model_unavailable")
            return
        session.add(SyncErrorLog(
            run_id=error_item["run_id"],
            mercado=error_item["mercado"],
            ticker=error_item["ticker"],
            tipo_erro=error_item["tipo_erro"],
            erro=error_item["erro"],
            segundos=error_item["segundos"],
            processado_em=error_item.get("processado_em") or datetime.utcnow(),
        ))

    def _normalize_market(self, mercado: str) -> str:
        normalized = str(mercado or "").strip().upper()
        if normalized not in VALID_MARKETS:
            raise ValueError(f"Mercado inválido: {mercado}")
        return normalized

    async def _upsert_payload(self, session: AsyncSession, mercado: str, payload: dict) -> None:
        model = self._model_for_market(mercado)
        values = self._map_payload(mercado, payload)
        values = self._filter_model_fields(model, values)

        if select is None:
            raise RuntimeError("SQLAlchemy não está disponível para upsert")

        stmt = select(model).where(
            model.ticker == values["ticker"],
            model.date == values["date"],
            model.source == SOURCE,
        )
        result = await session.execute(stmt)
        instance = result.scalar_one_or_none()

        if instance is None:
            session.add(model(**values))
            return

        for key, value in values.items():
            if key != "id":
                setattr(instance, key, value)

    def _model_for_market(self, mercado: str):
        self._normalize_market(mercado)
        model_by_market = {
            "FIIS": FiiFundamental,
            "ACOES": AcaoFundamental,
            "ETF": EtfFundamental,
            "BDR": BdrFundamental,
        }
        model = model_by_market[mercado]
        if model is None:
            raise RuntimeError(f"Model indisponível para mercado {mercado}")
        return model

    def _filter_model_fields(self, model: Any, values: dict) -> dict:
        columns = set(getattr(getattr(model, "__table__", None), "columns", {}).keys())
        if not columns:
            return values
        filtered = {}
        for key, value in values.items():
            if key in columns:
                filtered[key] = value
            else:
                logger.warning("investidor10_sync.ignored_missing_model_field", extra={"model": getattr(model, "__name__", str(model)), "field": key})
        return filtered

    def _base_values(self, payload: dict) -> dict:
        ticker = str(payload.get("ticker") or "").strip().upper()
        if not ticker:
            raise ValueError("Payload sem ticker")
        processed_date = _to_date(payload.get("data_processado")) or datetime.utcnow().date()
        return {
            "ticker": ticker,
            "name": payload.get("name") or ticker,
            "date": processed_date,
            "source": SOURCE,
            "coletado_em": datetime.utcnow(),
        }

    def _map_payload(self, mercado: str, payload: dict) -> dict:
        mercado = self._normalize_market(mercado)
        base = self._base_values(payload)
        mapping = {
            "FIIS": {
                "price": _to_decimal(payload.get("valor_atual_num")),
                "patrimonio_liq": _to_decimal(payload.get("patrimonio_num")),
                "pvp": _to_decimal(payload.get("p_vp_num")),
                "ultimo_rendimento": _to_decimal(payload.get("ultimo_rendimento_num")),
                "dy_12m": _to_decimal(payload.get("dividend_yield_num")),
                "num_cotistas": payload.get("numero_cotistas_num"),
                "taxa_adm": _to_decimal(payload.get("taxa_administracao_num")),
                "liquidez_diaria": _to_decimal(payload.get("liquidez_diaria_num")),
                "segmento": payload.get("segmento"),
                "tipo": payload.get("tipo_gestao"),
                "vacancia_fisica": _to_decimal(payload.get("vacancia_num")),
            },
            "ACOES": {
                "price": _to_decimal(payload.get("valor_atual_num")),
                "market_cap": _to_decimal(payload.get("valor_mercado_num")),
                "pl": _to_decimal(payload.get("p_l_num")),
                "pvp": _to_decimal(payload.get("p_vp_num")),
                "psr": _to_decimal(payload.get("psr_num")),
                "ev_ebitda": _to_decimal(payload.get("ev_ebitda_num")),
                "roe": _to_decimal(payload.get("roe_num")),
                "roic": _to_decimal(payload.get("roic_num")),
                "margem_liquida": _to_decimal(payload.get("margem_liquida_num")),
                "cagr_receita_5a": _to_decimal(payload.get("cagr_receita_5a_num")),
                "cagr_lucro_5a": _to_decimal(payload.get("cagr_lucro_5a_num")),
                "dy_12m": _to_decimal(payload.get("dividend_yield_num")),
                "divida_liq_ebitda": _to_decimal(payload.get("divida_liquida_ebitda_num")),
                "volume_medio_diario": _to_decimal(payload.get("liquidez_media_diaria_num")),
                "setor": payload.get("setor"),
                "subsetor": payload.get("subsetor"),
            },
            "ETF": {
                "price": _to_decimal(payload.get("valor_atual_num")),
                "patrimonio_liq": _to_decimal(payload.get("patrimonio_num")),
                "indice_replicado": payload.get("indice_referencia"),
                "tipo": payload.get("tipo"),
                "taxa_adm": _to_decimal(payload.get("taxa_num")),
                "retorno_12m": _to_decimal(payload.get("variacao_12m_num")),
                "retorno_24m": _to_decimal(payload.get("rentabilidade_2a_num")),
                "volume_medio_diario": _to_decimal(payload.get("liquidez_media_diaria_num")),
            },
            "BDR": {
                "price": _to_decimal(payload.get("preco_atual_num")),
                "market_cap": _to_decimal(payload.get("valor_mercado_num")),
                "pl": _to_decimal(payload.get("p_l_num")),
                "pvp": _to_decimal(payload.get("p_vpa_num")),
                "dy_12m": _to_decimal(payload.get("dividend_yield_num")),
                "volume_medio_diario_brl": _to_decimal(payload.get("liquidez_media_diaria_num")),
                "pais_origem": payload.get("pais_origem"),
                "moeda_origem": payload.get("moeda"),
            },
        }[mercado]
        return {**base, **mapping}
