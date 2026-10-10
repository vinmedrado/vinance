from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

from backend.app.market.catalogs import ACOES, BDRS, ETFS, FIIS
from backend.app.market.models.sync_error_log import SyncErrorLog
from backend.app.market.services.investidor10_sync import (
    ERROR_BLOQUEIO,
    ERROR_HTTP,
    ERROR_PARSE,
    ERROR_TIMEOUT,
    Investidor10SyncService,
)


class FakeProvider:
    def _scrape_by_market(self, mercado: str, ticker: str) -> dict:
        if ticker == "TIMEOUT11":
            raise TimeoutError("request timeout")
        return {"ticker": ticker, "name": ticker, "data_processado": "2026-06-09"}


class FakeSession:
    def __init__(self) -> None:
        self.items = []
        self.committed = False
        self.rolled_back = False

    def add(self, item) -> None:
        self.items.append(item)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def test_catalog_imports_use_broad_real_catalogs() -> None:
    assert len(FIIS) > 100
    assert len(ACOES) > 300
    assert len(ETFS) > 20
    assert len(BDRS) > 100

    for expected in ["MXRF11", "HGLG11", "KNRI11", "XPLG11", "VISC11"]:
        assert expected in FIIS
    for expected in ["PETR4", "VALE3", "ITUB4", "BBAS3", "WEGE3"]:
        assert expected in ACOES
    for expected in ["BOVA11", "IVVB11", "SMAL11", "HASH11"]:
        assert expected in ETFS
    for expected in ["AAPL34", "MSFT34", "GOGL34", "AMZO34"]:
        assert expected in BDRS


def test_catalogs_are_sanitized_deduplicated_and_sorted() -> None:
    for catalog in [FIIS, ACOES, ETFS, BDRS]:
        assert catalog == sorted(set(catalog))
        assert all(ticker == ticker.strip().upper() for ticker in catalog)
        assert all(ticker for ticker in catalog)


def test_error_classification_contract() -> None:
    service = Investidor10SyncService(provider=FakeProvider())
    assert service.classify_error("request timeout") == ERROR_TIMEOUT
    assert service.classify_error("Bloqueado por proteção do site") == ERROR_BLOQUEIO
    assert service.classify_error("HTTP 503") == ERROR_HTTP
    assert service.classify_error("invalid literal for int") == ERROR_PARSE


def test_retry_intelligence_contract() -> None:
    service = Investidor10SyncService(provider=FakeProvider())
    assert service.should_retry("request timeout") is True
    assert service.should_retry("connection reset") is True
    assert service.should_retry("HTTP 503") is True
    assert service.should_retry("HTTP 404") is False
    assert service.should_retry("Bloqueado por proteção do site") is False
    assert service.should_retry("invalid literal for int") is False


def test_workers_are_limited() -> None:
    service = Investidor10SyncService(provider=FakeProvider())
    assert service._sanitize_workers(None) == 2
    assert service._sanitize_workers(0) == 2
    assert service._sanitize_workers(1) == 1
    assert service._sanitize_workers(99) == 4


def test_semaphore_is_used_in_sync_market() -> None:
    source = inspect.getsource(Investidor10SyncService.sync_market)
    assert "asyncio.Semaphore" in source
    assert "async with semaphore" in source


def test_benchmark_calculation() -> None:
    service = Investidor10SyncService(provider=FakeProvider())
    benchmark = service._benchmark(total=10, ok=8, erros=2, tempo_segundos=120, errors_by_type={ERROR_BLOQUEIO: 1, ERROR_TIMEOUT: 1})
    assert benchmark["throughput"] == 5
    assert benchmark["ativos_por_minuto"] == 5
    assert benchmark["tempo_total"] == 120
    assert benchmark["sucesso_pct"] == 80
    assert benchmark["erros_pct"] == 20
    assert benchmark["bloqueios"] == 1
    assert benchmark["timeouts"] == 1


def test_sync_error_log_model_contract() -> None:
    columns = SyncErrorLog.__table__.columns.keys()
    for column in ["id", "run_id", "mercado", "ticker", "tipo_erro", "erro", "segundos", "processado_em"]:
        assert column in columns


def test_tasks_by_market_import_and_names() -> None:
    from backend.app.market import tasks

    assert tasks.sync_fiis.name == "market.sync_fiis"
    assert tasks.sync_acoes.name == "market.sync_acoes"
    assert tasks.sync_etfs.name == "market.sync_etfs"
    assert tasks.sync_bdrs.name == "market.sync_bdrs"
    assert tasks.sync_all_investidor10.name == "market.sync_all_investidor10"


def test_migration_exists_for_sync_error_log() -> None:
    migration = Path("backend/alembic/versions/0008_create_sync_error_log.py")
    assert migration.exists()
    content = migration.read_text(encoding="utf-8")
    assert "sync_error_log" in content
    assert "0007_create_sync_log" in content


def test_incremental_sync_deduplicates_tickers_and_calculates_throughput(monkeypatch) -> None:
    service = Investidor10SyncService(provider=FakeProvider())
    session = FakeSession()

    async def fake_upsert(_session, _mercado, _payload):
        return None

    monkeypatch.setattr(service, "_upsert_payload", fake_upsert)
    result = asyncio.run(service.sync_market(session, "FIIS", ["MXRF11", "MXRF11", "TIMEOUT11"], workers=9, throttle_seconds=0, max_attempts=1))

    assert result["total"] == 2
    assert result["ok"] == 1
    assert result["erros"] == 1
    assert result["workers"] == 4
    assert result["throughput"] >= 0
    assert result["timeouts"] == 1
    assert session.committed is True
    assert any(isinstance(item, SyncErrorLog) for item in session.items)
