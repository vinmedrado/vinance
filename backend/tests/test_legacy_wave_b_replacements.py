from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_obsolete_sqlite_readers_are_retired() -> None:
    retired_readers = (
        ROOT / "services" / "intelligence_bi_service.py",
        ROOT / "services" / "strategy_comparator.py",
    )

    assert all(not path.exists() for path in retired_readers)


def test_official_postgresql_and_trading_replacements_are_versioned() -> None:
    replacements = (
        ROOT / "backend" / "app" / "investment_decisions" / "service.py",
        ROOT / "backend" / "app" / "investment_performance" / "service.py",
        ROOT / "backend" / "app" / "investment_alerts" / "service.py",
        ROOT / "backend" / "trading" / "backtesting_v2" / "comparison.py",
    )

    assert all(path.is_file() for path in replacements)


def test_official_replacement_contracts_import_without_legacy_database() -> None:
    from backend.app.investment_alerts.service import (
        create_monitoring_subscription,
        list_monitoring_subscriptions,
    )
    from backend.app.investment_decisions.service import (
        get_decision_metrics,
        list_decision_history,
    )
    from backend.app.investment_performance.service import (
        get_decision_performance,
        get_performance_summary,
    )
    from backend.trading.backtesting_v2.comparison import compare_thresholds

    contracts = (
        create_monitoring_subscription,
        list_monitoring_subscriptions,
        get_decision_metrics,
        list_decision_history,
        get_decision_performance,
        get_performance_summary,
        compare_thresholds,
    )

    assert all(callable(contract) for contract in contracts)


def test_official_runtime_remains_free_from_sqlite_compatibility() -> None:
    runtime_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "backend" / "app" / "main.py",
            ROOT / "backend" / "app" / "api" / "v1" / "router.py",
            ROOT / "backend" / "app" / "core" / "celery.py",
        )
    )

    assert "pg_compat" not in runtime_sources
    assert "sqlite3" not in runtime_sources
    assert "services.intelligence_bi_service" not in runtime_sources
    assert "services.strategy_comparator" not in runtime_sources
