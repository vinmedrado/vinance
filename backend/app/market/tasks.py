from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Coroutine

from backend.app.core.celery import celery_app
from sqlalchemy import func, select

from backend.app.core.database import AsyncSessionLocal, engine
from backend.app.core.pretty_logs import (
    log_task_error,
    log_task_start,
    log_task_success,
    log_task_warning,
)
from backend.app.market.services.catalog_service import CatalogService
from backend.app.market.services.coingecko_sync import CoinGeckoSyncService
from backend.app.market.services.investidor10_sync import Investidor10SyncService
from backend.app.intelligence.services.asset_score_service import calculate_all_asset_scores
from backend.app.intelligence.services.recommendation_guardrail_service import calculate_all_recommendation_guardrails
from backend.app.intelligence.services.trend_signal_service import calculate_all_trend_signals
from backend.app.intelligence.asset_trend_signal_model import AssetTrendSignal

logger = logging.getLogger(__name__)


async def _run_with_cleanup(coro: Coroutine[Any, Any, dict]) -> dict:
    """Execute a task coroutine and dispose SQLAlchemy async pools before loop shutdown."""
    try:
        return await coro
    finally:
        await engine.dispose()


def _run_async(coro: Coroutine[Any, Any, dict]) -> dict:
    """Run async sync services from sync Celery tasks with deterministic DB cleanup."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_run_with_cleanup(coro))

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, _run_with_cleanup(coro))
        return future.result()



def _elapsed_seconds(started_at: float) -> str:
    return f"{time.perf_counter() - started_at:.2f}s"


def _success_pct(result: dict) -> float:
    total = int(result.get("total") or 0)
    ok = int(result.get("ok") or 0)
    return (ok / max(total, 1)) * 100


def _guardrail_counts(result: dict) -> dict[str, int]:
    counts = {"APPROVED": 0, "WARNING": 0, "BLOCKED": 0}
    for market_result in result.get("markets") or []:
        for status, value in (market_result.get("status_counts") or {}).items():
            counts[str(status).upper()] = counts.get(str(status).upper(), 0) + int(value or 0)
    return counts


async def _trend_counts(session) -> dict[str, int]:
    latest_date_result = await session.execute(select(func.max(AssetTrendSignal.date)))
    latest_date = latest_date_result.scalar_one_or_none()
    counts = {"UPTREND": 0, "SIDEWAYS": 0, "DOWNTREND": 0, "INSUFFICIENT_HISTORY": 0}
    if latest_date is None:
        return counts
    result = await session.execute(
        select(AssetTrendSignal.trend_label, func.count(AssetTrendSignal.id))
        .where(AssetTrendSignal.date == latest_date)
        .group_by(AssetTrendSignal.trend_label)
    )
    for trend_label, count in result.all():
        counts[str(trend_label).upper()] = int(count or 0)
    return counts




@celery_app.task(name="market.calculate_asset_scores", queue="intelligence")
def calculate_asset_scores() -> dict:
    return _run_async(_calculate_asset_scores())


async def _calculate_asset_scores() -> dict:
    started_at = time.perf_counter()
    log_task_start(logger, "🧠 [INTELLIGENCE] Iniciando Asset Scores", Fonte="vinance_score_v1")
    session = AsyncSessionLocal()
    try:
        try:
            result = await calculate_all_asset_scores(session)
            logger.info("market_task.calculate_asset_scores.finished", extra=result)
            log_task_success(
                logger,
                "🧠 [INTELLIGENCE] Asset Scores finalizado",
                Status=result.get("status", "SUCCESS"),
                Salvos=result.get("saved", 0),
                Tempo=_elapsed_seconds(started_at),
            )
            return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("market_task.calculate_asset_scores.failed", extra={"error": str(exc)})
            log_task_error(
                logger,
                "🧠 [INTELLIGENCE] Asset Scores falhou",
                Status="FAILED",
                Erro=str(exc),
                Tempo=_elapsed_seconds(started_at),
            )
            return {"status": "FAILED", "source": "vinance_score_v1", "error": str(exc), "saved": 0}
    finally:
        await session.close()



@celery_app.task(name="market.calculate_recommendation_guardrails", queue="intelligence")
def calculate_recommendation_guardrails() -> dict:
    return _run_async(_calculate_recommendation_guardrails())


async def _calculate_recommendation_guardrails() -> dict:
    started_at = time.perf_counter()
    log_task_start(logger, "🛡️ [GUARDRAILS] Iniciando regras de recomendação", Fonte="vinance_guardrail_v1")
    session = AsyncSessionLocal()
    try:
        try:
            result = await calculate_all_recommendation_guardrails(session)
            logger.info("market_task.calculate_recommendation_guardrails.finished", extra=result)
            counts = _guardrail_counts(result)
            log_task_success(
                logger,
                "🛡️ [GUARDRAILS] Regras de recomendação finalizadas",
                Status=result.get("status", "SUCCESS"),
                Approved=counts.get("APPROVED", 0),
                Warning=counts.get("WARNING", 0),
                Blocked=counts.get("BLOCKED", 0),
                Salvos=result.get("saved", 0),
                Tempo=_elapsed_seconds(started_at),
            )
            return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("market_task.calculate_recommendation_guardrails.failed", extra={"error": str(exc)})
            log_task_error(
                logger,
                "🛡️ [GUARDRAILS] Regras de recomendação falharam",
                Status="FAILED",
                Erro=str(exc),
                Tempo=_elapsed_seconds(started_at),
            )
            return {"status": "FAILED", "source": "vinance_guardrail_v1", "error": str(exc), "saved": 0}
    finally:
        await session.close()



@celery_app.task(name="market.calculate_trend_signals", queue="intelligence")
def calculate_trend_signals() -> dict:
    return _run_async(_calculate_trend_signals())


async def _calculate_trend_signals() -> dict:
    started_at = time.perf_counter()
    log_task_start(logger, "📈 [TREND] Iniciando Trend Signals", Fonte="vinance_trend_v1")
    session = AsyncSessionLocal()
    try:
        try:
            result = await calculate_all_trend_signals(session)
            logger.info("market_task.calculate_trend_signals.finished", extra=result)
            counts = await _trend_counts(session)
            log_task_success(
                logger,
                "📈 [TREND] Trend Signals finalizado",
                Status=result.get("status", "SUCCESS"),
                Uptrend=counts.get("UPTREND", 0),
                Sideways=counts.get("SIDEWAYS", 0),
                Downtrend=counts.get("DOWNTREND", 0),
                Insufficient_History=counts.get("INSUFFICIENT_HISTORY", 0),
                Salvos=result.get("saved", 0),
                Tempo=_elapsed_seconds(started_at),
            )
            return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("market_task.calculate_trend_signals.failed", extra={"error": str(exc)})
            log_task_error(
                logger,
                "📈 [TREND] Trend Signals falhou",
                Status="FAILED",
                Erro=str(exc),
                Tempo=_elapsed_seconds(started_at),
            )
            return {"status": "FAILED", "source": "vinance_trend_v1", "error": str(exc), "saved": 0}
    finally:
        await session.close()

@celery_app.task(name="market.sync_cripto_coingecko", queue="market")
def sync_cripto_coingecko(
    ids: list[str] | None = None,
    vs_currency: str = "brl",
    per_page: int = 250,
    pages: int = 4,
) -> dict:
    return _run_async(_sync_cripto_coingecko(ids=ids, vs_currency=vs_currency, per_page=per_page, pages=pages))


async def _sync_cripto_coingecko(
    ids: list[str] | None = None,
    vs_currency: str = "brl",
    per_page: int = 250,
    pages: int = 4,
) -> dict:
    started_at = time.perf_counter()
    total_expected = len(ids) if ids else int(per_page or 250) * int(pages or 4)
    log_task_start(
        logger,
        "[CRIPTO] Iniciando CoinGecko Sync",
        Fonte="CoinGecko",
        Total_Estimado=total_expected,
        Páginas=pages if not ids else "manual",
        Per_Page=per_page if not ids else "manual",
        Moeda=vs_currency,
    )
    logger.info(
        "market_task.sync_cripto_coingecko.started",
        extra={
            "mercado": "CRIPTO",
            "total_tickers": total_expected,
            "source_catalog": "coingecko_pagination" if not ids else "manual_parameter",
            "workers": None,
            "vs_currency": vs_currency,
            "per_page": per_page,
            "pages": pages,
        },
    )
    session = AsyncSessionLocal()
    try:
        try:
            service = CoinGeckoSyncService()
            if ids:
                result = await service.sync_markets(session, ids, vs_currency=vs_currency)
            else:
                result = await service.sync_markets_by_pages(
                    session,
                    vs_currency=vs_currency,
                    per_page=per_page,
                    pages=pages,
                )
            logger.info("market_task.sync_cripto_coingecko.finished", extra=result)
            log_task_success(
                logger,
                "[CRIPTO] CoinGecko Sync finalizado",
                Status=result.get("status", "SUCCESS"),
                Total=result.get("total", total_expected),
                OK=result.get("ok", result.get("total", 0)),
                Erros=result.get("erros", 0),
                Sucesso=f"{float(result.get('sucesso_pct', _success_pct(result)) or 0.0):.1f}%",
                Tempo=_elapsed_seconds(started_at),
            )
            return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("market_task.sync_cripto_coingecko.failed", extra={"error": str(exc)})
            total = len(ids or []) or int(per_page or 250) * int(pages or 4)
            log_task_error(
                logger,
                "[CRIPTO] CoinGecko Sync falhou",
                Status="FAILED",
                Total=total,
                Erro=str(exc),
                Tempo=_elapsed_seconds(started_at),
            )
            return _failed_summary("COINGECKO", "CRIPTO", total, str(exc))
    finally:
        await session.close()


@celery_app.task(name="market.sync_fiis", queue="market")
def sync_fiis(tickers: list[str] | None = None, workers: int | None = None) -> dict:
    return _run_async(_sync_investidor10_market("FIIS", tickers, workers=workers))


@celery_app.task(name="market.sync_acoes", queue="market")
def sync_acoes(tickers: list[str] | None = None, workers: int | None = None) -> dict:
    return _run_async(_sync_investidor10_market("ACOES", tickers, workers=workers))


@celery_app.task(name="market.sync_etfs", queue="market")
def sync_etfs(tickers: list[str] | None = None, workers: int | None = None) -> dict:
    return _run_async(_sync_investidor10_market("ETF", tickers, workers=workers))


@celery_app.task(name="market.sync_bdrs", queue="market")
def sync_bdrs(tickers: list[str] | None = None, workers: int | None = None) -> dict:
    return _run_async(_sync_investidor10_market("BDR", tickers, workers=workers))


@celery_app.task(name="market.sync_fiis_investidor10", queue="market")
def sync_fiis_investidor10(tickers: list[str] | None = None, workers: int | None = None) -> dict:
    return _run_async(_sync_investidor10_market("FIIS", tickers, workers=workers))


@celery_app.task(name="market.sync_acoes_investidor10", queue="market")
def sync_acoes_investidor10(tickers: list[str] | None = None, workers: int | None = None) -> dict:
    return _run_async(_sync_investidor10_market("ACOES", tickers, workers=workers))


@celery_app.task(name="market.sync_etfs_investidor10", queue="market")
def sync_etfs_investidor10(tickers: list[str] | None = None, workers: int | None = None) -> dict:
    return _run_async(_sync_investidor10_market("ETF", tickers, workers=workers))


@celery_app.task(name="market.sync_bdrs_investidor10", queue="market")
def sync_bdrs_investidor10(tickers: list[str] | None = None, workers: int | None = None) -> dict:
    return _run_async(_sync_investidor10_market("BDR", tickers, workers=workers))


@celery_app.task(name="market.sync_all_investidor10", queue="market")
def sync_all_investidor10(workers: int | None = None) -> dict:
    return _run_async(_sync_all_investidor10(workers=workers))


async def _sync_investidor10_market(mercado: str, tickers: list[str] | None = None, workers: int | None = None) -> dict:
    session = AsyncSessionLocal()
    resolved_tickers: list[str] = []
    try:
        try:
            source_catalog = "manual_parameter" if tickers is not None else "asset_catalog"
            resolved_tickers = list(tickers) if tickers is not None else await CatalogService().list_tickers(session, mercado)
            logger.info(
                "market_task.sync_investidor10.started",
                extra={
                    "mercado": mercado,
                    "total_tickers": len(resolved_tickers),
                    "source_catalog": source_catalog,
                    "workers": workers,
                },
            )
            if not resolved_tickers:
                message = f"asset_catalog vazio para mercado {mercado}; sync Investidor10 ignorado sem fallback runtime"
                logger.warning("market_task.sync_investidor10.skipped_empty_catalog", extra={"mercado": mercado, "error": message})
                return _skipped_summary("INVESTIDOR10", mercado, message)

            result = await Investidor10SyncService().sync_market(session, mercado, resolved_tickers, workers=workers)
            logger.info("market_task.sync_investidor10.finished", extra=result)
            return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("market_task.sync_investidor10.failed", extra={"mercado": mercado, "error": str(exc)})
            return _failed_summary("INVESTIDOR10", mercado, len(resolved_tickers), str(exc))
    finally:
        await session.close()


async def _sync_all_investidor10(workers: int | None = None) -> dict:
    started_at = time.perf_counter()
    markets = ["FIIS", "ACOES", "ETF", "BDR"]
    log_task_start(
        logger,
        "[INVESTIDOR10] Iniciando Sync diário",
        Fonte="Investidor10",
        Mercados=", ".join(markets),
        Workers=workers or "default",
    )
    logger.info("market_task.sync_all_investidor10.started", extra={"workers": workers})

    results: list[dict] = []
    for mercado in markets:
        results.append(await _sync_investidor10_market(mercado, workers=workers))

    total = sum(int(item.get("total") or 0) for item in results)
    ok = sum(int(item.get("ok") or 0) for item in results)
    erros = sum(int(item.get("erros") or 0) for item in results)
    tempo_total = sum(float(item.get("tempo_total") or item.get("tempo_segundos") or 0.0) for item in results)
    sucesso_pct = (ok / max(total, 1)) * 100
    erros_pct = (erros / max(total, 1)) * 100
    throughput = (total / tempo_total) * 60 if tempo_total > 0 else 0.0

    skipped = sum(1 for item in results if item.get("status") == "SKIPPED")
    if skipped == len(results):
        status = "SKIPPED"
    elif erros == 0:
        status = "SUCCESS"
    elif ok > 0:
        status = "PARTIAL_SUCCESS"
    else:
        status = "FAILED"

    summary = {
        "source": "INVESTIDOR10",
        "mercado": "ALL",
        "status": status,
        "total": total,
        "ok": ok,
        "erros": erros,
        "sucesso_pct": sucesso_pct,
        "erros_pct": erros_pct,
        "tempo_total": tempo_total,
        "throughput": throughput,
        "ativos_por_minuto": throughput,
        "workers": workers,
        "results": results,
    }
    logger.info("market_task.sync_all_investidor10.finished", extra=summary)
    if status in {"SUCCESS", "PARTIAL_SUCCESS"}:
        log_task_success(
            logger,
            "[INVESTIDOR10] Sync diário finalizado",
            Status=status,
            Total=total,
            OK=ok,
            Erros=erros,
            Sucesso=f"{sucesso_pct:.1f}%",
            Throughput=f"{throughput:.2f} ativos/min",
            Tempo=_elapsed_seconds(started_at),
        )
    elif status == "SKIPPED":
        log_task_warning(
            logger,
            "[INVESTIDOR10] Sync diário ignorado",
            Status=status,
            Total=total,
            Tempo=_elapsed_seconds(started_at),
        )
    else:
        log_task_error(
            logger,
            "[INVESTIDOR10] Sync diário falhou",
            Status=status,
            Total=total,
            Erros=erros,
            Tempo=_elapsed_seconds(started_at),
        )
    return summary


def _skipped_summary(source: str, mercado: str, message: str) -> dict:
    return {
        "source": source,
        "mercado": mercado,
        "status": "SKIPPED",
        "total": 0,
        "ok": 0,
        "erros": 0,
        "sucesso_pct": 0.0,
        "erros_pct": 0.0,
        "tempo_segundos": 0.0,
        "tempo_total": 0.0,
        "throughput": 0.0,
        "ativos_por_minuto": 0.0,
        "error_message": message,
    }


def _failed_summary(source: str, mercado: str, total: int, error_message: str) -> dict:
    return {
        "source": source,
        "mercado": mercado,
        "status": "FAILED",
        "total": total,
        "ok": 0,
        "erros": total,
        "sucesso_pct": 0.0,
        "erros_pct": 100.0 if total else 0.0,
        "tempo_segundos": 0.0,
        "tempo_total": 0.0,
        "throughput": 0.0,
        "ativos_por_minuto": 0.0,
        "error_message": error_message,
    }
