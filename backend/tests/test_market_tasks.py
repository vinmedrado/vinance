from __future__ import annotations

from pathlib import Path

from celery.schedules import crontab

from backend.app.core.celery import celery_app
from backend.app.market import tasks


def test_import_all_market_tasks() -> None:
    assert tasks.sync_cripto_coingecko is not None
    assert tasks.sync_fiis_investidor10 is not None
    assert tasks.sync_acoes_investidor10 is not None
    assert tasks.sync_etfs_investidor10 is not None
    assert tasks.sync_bdrs_investidor10 is not None
    assert tasks.sync_all_investidor10 is not None


def test_task_names() -> None:
    assert tasks.sync_cripto_coingecko.name == "market.sync_cripto_coingecko"
    assert tasks.sync_fiis_investidor10.name == "market.sync_fiis_investidor10"
    assert tasks.sync_acoes_investidor10.name == "market.sync_acoes_investidor10"
    assert tasks.sync_etfs_investidor10.name == "market.sync_etfs_investidor10"
    assert tasks.sync_bdrs_investidor10.name == "market.sync_bdrs_investidor10"
    assert tasks.sync_all_investidor10.name == "market.sync_all_investidor10"


def test_beat_schedule_contains_coingecko_every_10_min() -> None:
    item = celery_app.conf.beat_schedule["market-sync-cripto-coingecko-every-10-min"]
    assert item["task"] == "market.sync_cripto_coingecko"
    assert isinstance(item["schedule"], crontab)
    assert item["schedule"]._orig_minute == "*/10"


def test_beat_schedule_contains_investidor10_21h() -> None:
    item = celery_app.conf.beat_schedule["market-sync-investidor10-daily-after-close"]
    assert item["task"] == "market.sync_all_investidor10"
    assert isinstance(item["schedule"], crontab)
    assert item["schedule"]._orig_hour == 21
    assert item["schedule"]._orig_minute == 0


def test_daily_schedules_use_crontab_not_int() -> None:
    for item in celery_app.conf.beat_schedule.values():
        assert not isinstance(item["schedule"], int)
        assert isinstance(item["schedule"], crontab)


def test_market_task_routes_queue_market() -> None:
    routes = celery_app.conf.task_routes
    expected_tasks = [
        "market.sync_cripto_coingecko",
        "market.sync_fiis_investidor10",
        "market.sync_acoes_investidor10",
        "market.sync_etfs_investidor10",
        "market.sync_bdrs_investidor10",
        "market.sync_all_investidor10",
    ]
    for task_name in expected_tasks:
        assert routes[task_name]["queue"] == "market"


def test_run_async_disposes_engine(monkeypatch) -> None:
    disposed = {"called": False}

    async def fake_dispose() -> None:
        disposed["called"] = True

    class FakeEngine:
        dispose = staticmethod(fake_dispose)

    async def sample() -> dict:
        return {"status": "SUCCESS"}

    monkeypatch.setattr(tasks, "engine", FakeEngine())

    result = tasks._run_async(sample())

    assert result == {"status": "SUCCESS"}
    assert disposed["called"] is True


def test_run_async_disposes_engine_when_coroutine_fails(monkeypatch) -> None:
    disposed = {"called": False}

    async def fake_dispose() -> None:
        disposed["called"] = True

    class FakeEngine:
        dispose = staticmethod(fake_dispose)

    async def sample() -> dict:
        raise RuntimeError("boom")

    monkeypatch.setattr(tasks, "engine", FakeEngine())

    try:
        tasks._run_async(sample())
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:  # pragma: no cover
        raise AssertionError("_run_async should propagate coroutine exceptions")

    assert disposed["called"] is True


def test_task_no_longer_defines_fixed_crypto_smoke_list() -> None:
    assert not hasattr(tasks, "DEFAULT_CRIPTO_IDS")


async def _fake_sync_by_pages(session, vs_currency="brl", per_page=250, pages=4):
    return {"status": "SUCCESS", "total": 1000, "ok": 1000, "erros": 0, "pages": pages, "per_page": per_page}


async def _fake_sync_by_ids(session, ids, vs_currency="brl"):
    return {"status": "SUCCESS", "total": len(ids), "ok": len(ids), "erros": 0, "ids": ids}


def test_sync_cripto_coingecko_default_uses_paged_service(monkeypatch) -> None:
    called = {"pages": False, "ids": False}

    class FakeService:
        async def sync_markets_by_pages(self, session, vs_currency="brl", per_page=250, pages=4):
            called["pages"] = True
            return await _fake_sync_by_pages(session, vs_currency, per_page, pages)

        async def sync_markets(self, session, ids, vs_currency="brl"):
            called["ids"] = True
            return await _fake_sync_by_ids(session, ids, vs_currency)

    class FakeSession:
        async def close(self):
            pass

    monkeypatch.setattr(tasks, "CoinGeckoSyncService", FakeService)
    monkeypatch.setattr(tasks, "AsyncSessionLocal", lambda: FakeSession())

    result = tasks._run_async(tasks._sync_cripto_coingecko())

    assert result["total"] == 1000
    assert result["pages"] == 4
    assert called == {"pages": True, "ids": False}


def test_sync_cripto_coingecko_still_accepts_explicit_partial_id_list(monkeypatch) -> None:
    called = {"pages": False, "ids": False}

    class FakeService:
        async def sync_markets_by_pages(self, session, vs_currency="brl", per_page=250, pages=4):
            called["pages"] = True
            return await _fake_sync_by_pages(session, vs_currency, per_page, pages)

        async def sync_markets(self, session, ids, vs_currency="brl"):
            called["ids"] = True
            return await _fake_sync_by_ids(session, ids, vs_currency)

    class FakeSession:
        async def close(self):
            pass

    monkeypatch.setattr(tasks, "CoinGeckoSyncService", FakeService)
    monkeypatch.setattr(tasks, "AsyncSessionLocal", lambda: FakeSession())

    result = tasks._run_async(tasks._sync_cripto_coingecko(ids=["solana", "cardano"]))

    assert result["ids"] == ["solana", "cardano"]
    assert called == {"pages": False, "ids": True}


def test_investidor10_tasks_do_not_expose_runtime_python_catalogs() -> None:
    assert not hasattr(tasks, "DEFAULT_FIIS_TICKERS")
    assert not hasattr(tasks, "DEFAULT_ACOES_TICKERS")
    assert not hasattr(tasks, "DEFAULT_ETF_TICKERS")
    assert not hasattr(tasks, "DEFAULT_BDR_TICKERS")
    assert not hasattr(tasks, "FIIS")
    assert not hasattr(tasks, "ACOES")
    assert not hasattr(tasks, "ETFS")
    assert not hasattr(tasks, "BDRS")


def test_sync_investidor10_market_uses_catalog_service_when_tickers_are_not_explicit(monkeypatch) -> None:
    calls = {"catalog": [], "sync": []}

    class FakeCatalogService:
        async def list_tickers(self, session, market):
            calls["catalog"].append(market)
            return ["MXRF11", "HGLG11"]

    class FakeInvestidor10SyncService:
        async def sync_market(self, session, mercado, tickers, workers=None):
            calls["sync"].append((mercado, tickers, workers))
            return {"status": "SUCCESS", "total": len(tickers), "ok": len(tickers), "erros": 0}

    class FakeSession:
        async def close(self):
            pass

    monkeypatch.setattr(tasks, "CatalogService", FakeCatalogService)
    monkeypatch.setattr(tasks, "Investidor10SyncService", FakeInvestidor10SyncService)
    monkeypatch.setattr(tasks, "AsyncSessionLocal", lambda: FakeSession())

    result = tasks._run_async(tasks._sync_investidor10_market("FIIS", workers=2))

    assert result["status"] == "SUCCESS"
    assert calls["catalog"] == ["FIIS"]
    assert calls["sync"] == [("FIIS", ["MXRF11", "HGLG11"], 2)]


def test_sync_investidor10_market_uses_explicit_tickers_without_catalog(monkeypatch) -> None:
    calls = {"catalog": False, "sync": []}

    class FakeCatalogService:
        async def list_tickers(self, session, market):  # pragma: no cover
            calls["catalog"] = True
            return ["SHOULD_NOT_USE"]

    class FakeInvestidor10SyncService:
        async def sync_market(self, session, mercado, tickers, workers=None):
            calls["sync"].append((mercado, tickers, workers))
            return {"status": "SUCCESS", "total": len(tickers), "ok": len(tickers), "erros": 0}

    class FakeSession:
        async def close(self):
            pass

    monkeypatch.setattr(tasks, "CatalogService", FakeCatalogService)
    monkeypatch.setattr(tasks, "Investidor10SyncService", FakeInvestidor10SyncService)
    monkeypatch.setattr(tasks, "AsyncSessionLocal", lambda: FakeSession())

    result = tasks._run_async(tasks._sync_investidor10_market("FIIS", ["MXRF11"], workers=1))

    assert result["status"] == "SUCCESS"
    assert calls["catalog"] is False
    assert calls["sync"] == [("FIIS", ["MXRF11"], 1)]


def test_sync_investidor10_market_skips_empty_catalog_without_fallback(monkeypatch) -> None:
    calls = {"sync": False}

    class FakeCatalogService:
        async def list_tickers(self, session, market):
            return []

    class FakeInvestidor10SyncService:
        async def sync_market(self, session, mercado, tickers, workers=None):  # pragma: no cover
            calls["sync"] = True
            return {}

    class FakeSession:
        async def close(self):
            pass

    monkeypatch.setattr(tasks, "CatalogService", FakeCatalogService)
    monkeypatch.setattr(tasks, "Investidor10SyncService", FakeInvestidor10SyncService)
    monkeypatch.setattr(tasks, "AsyncSessionLocal", lambda: FakeSession())

    result = tasks._run_async(tasks._sync_investidor10_market("FIIS"))

    assert result["status"] == "SKIPPED"
    assert result["total"] == 0
    assert "asset_catalog vazio" in result["error_message"]
    assert calls["sync"] is False


def test_market_tasks_source_has_no_runtime_small_limits_or_python_catalog_imports() -> None:
    source = Path("backend/app/market/tasks.py").read_text(encoding="utf-8")
    forbidden = [
        "from backend.app.market.catalogs",
        "DEFAULT_FIIS",
        "DEFAULT_ACOES",
        "DEFAULT_ETF",
        "DEFAULT_BDR",
        "DEFAULT_CRIPTO",
        "[:5]",
        "[:4]",
        "limit=5",
        "ids=bitcoin,ethereum",
        "['bitcoin', 'ethereum']",
        '["bitcoin", "ethereum"]',
        "smoke",
    ]
    for pattern in forbidden:
        assert pattern not in source


def test_sync_all_investidor10_uses_catalog_for_each_market_with_full_totals(monkeypatch) -> None:
    catalog = {
        "FIIS": [f"FII{i:03d}11" for i in range(450)],
        "ACOES": [f"ACAO{i:03d}" for i in range(330)],
        "ETF": [f"ETF{i:04d}11" for i in range(2387)],
        "BDR": [f"BDR{i:03d}34" for i in range(696)],
    }
    calls = {"catalog": [], "sync": []}

    class FakeCatalogService:
        async def list_tickers(self, session, market):
            calls["catalog"].append(market)
            return catalog[market]

    class FakeInvestidor10SyncService:
        async def sync_market(self, session, mercado, tickers, workers=None):
            calls["sync"].append((mercado, len(tickers), workers))
            return {"status": "SUCCESS", "total": len(tickers), "ok": len(tickers), "erros": 0, "tempo_total": 1.0}

    class FakeSession:
        async def close(self):
            pass

    monkeypatch.setattr(tasks, "CatalogService", FakeCatalogService)
    monkeypatch.setattr(tasks, "Investidor10SyncService", FakeInvestidor10SyncService)
    monkeypatch.setattr(tasks, "AsyncSessionLocal", lambda: FakeSession())

    result = tasks._run_async(tasks._sync_all_investidor10(workers=2))

    assert calls["catalog"] == ["FIIS", "ACOES", "ETF", "BDR"]
    assert calls["sync"] == [("FIIS", 450, 2), ("ACOES", 330, 2), ("ETF", 2387, 2), ("BDR", 696, 2)]
    assert result["total"] == 3863
    assert result["status"] == "SUCCESS"


def test_sync_fiis_investidor10_wrapper_calls_internal_coroutine_and_catalog(monkeypatch) -> None:
    calls = {"catalog": [], "sync": []}
    ten_tickers = [f"FII{i:02d}11" for i in range(10)]

    class FakeCatalogService:
        async def list_tickers(self, session, market):
            calls["catalog"].append(market)
            return ten_tickers

    class FakeInvestidor10SyncService:
        async def sync_market(self, session, mercado, tickers, workers=None):
            calls["sync"].append((mercado, len(tickers), workers))
            return {"status": "SUCCESS", "total": len(tickers), "ok": len(tickers), "erros": 0}

    class FakeSession:
        async def close(self):
            pass

    def forbidden_sync_fiis(*args, **kwargs):  # pragma: no cover
        raise AssertionError("sync_fiis_investidor10 must not call sync_fiis task internally")

    monkeypatch.setattr(tasks, "CatalogService", FakeCatalogService)
    monkeypatch.setattr(tasks, "Investidor10SyncService", FakeInvestidor10SyncService)
    monkeypatch.setattr(tasks, "AsyncSessionLocal", lambda: FakeSession())
    monkeypatch.setattr(tasks, "sync_fiis", forbidden_sync_fiis)

    result = tasks.sync_fiis_investidor10.run(workers=3)

    assert result["total"] == 10
    assert calls["catalog"] == ["FIIS"]
    assert calls["sync"] == [("FIIS", 10, 3)]


def test_investidor10_wrappers_do_not_call_other_celery_tasks() -> None:
    source = Path("backend/app/market/tasks.py").read_text(encoding="utf-8")
    forbidden = [
        "return sync_fiis",
        "return sync_acoes",
        "return sync_etfs",
        "return sync_bdrs",
    ]
    for pattern in forbidden:
        assert pattern not in source
