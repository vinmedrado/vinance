from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_superseded_analytics_and_trading_entry_points_are_absent() -> None:
    retired_paths = (
        ROOT / "backend" / "app" / "analysis" / "analysis_repository.py",
        ROOT / "backend" / "app" / "backtest" / "backtest_repository.py",
        ROOT / "backend" / "app" / "data_layer" / "repositories" / "sqlite_repository.py",
        ROOT / "backend" / "app" / "market" / "routers" / "market.py",
        ROOT / "backend" / "app" / "quant_intelligence" / "router.py",
        ROOT / "frontend" / "src" / "pages" / "QuantLab.tsx",
        ROOT / "frontend" / "src" / "services" / "quant.ts",
        ROOT / "services" / "catalog_pipeline_runs.py",
        ROOT / "services" / "market_data_pipeline_runs.py",
        ROOT / "services" / "pipeline_background_tasks.py",
    )

    assert all(not path.exists() for path in retired_paths)


def test_trading_v2_stack_and_artifact_contract_remain_versioned() -> None:
    preserved_paths = (
        ROOT / "backend" / "trading" / "feature_store" / "__init__.py",
        ROOT / "backend" / "trading" / "target_engine" / "__init__.py",
        ROOT / "backend" / "trading" / "ml_engine" / "__init__.py",
        ROOT / "backend" / "trading" / "prediction_engine" / "__init__.py",
        ROOT / "backend" / "trading" / "backtesting_v2" / "__init__.py",
        ROOT / "backend" / "trading" / "research_v2" / "__init__.py",
        ROOT / "backend" / "trading" / "validation_v2" / "__init__.py",
        ROOT / "backend" / "trading" / "paper_trading_v2" / "__init__.py",
        ROOT / "backend" / "trading" / "history_expansion_v2" / "__init__.py",
        ROOT / "backend" / "trading" / "scripts" / "experiment_campaign_v2.py",
        ROOT / "backend" / "trading" / "artifacts" / ".gitignore",
    )

    assert all(path.is_file() for path in preserved_paths)


def test_official_runtime_has_no_legacy_database_or_entry_point_imports() -> None:
    runtime_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "backend" / "app" / "main.py",
            ROOT / "backend" / "app" / "api" / "v1" / "router.py",
            ROOT / "backend" / "app" / "core" / "celery.py",
        )
    )
    forbidden = (
        "pg_compat",
        "sqlite3",
        "backend.app.analysis",
        "backend.app.backtest",
        "backend.app.data_layer",
        "backend.app.quant_intelligence",
        "backend.app.market.routers",
        "workers.tasks",
        "CREATE TABLE",
        "ALTER TABLE",
        "DROP TABLE",
        "PRAGMA",
        "sqlite_master",
    )

    assert all(token not in runtime_sources for token in forbidden)


def test_backtest_history_schema_is_written_by_trading_pipeline() -> None:
    pipeline_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "backend" / "trading" / "scripts" / "run_pipeline.py",
            ROOT / "backend" / "trading" / "scripts" / "run_research_pipeline.py",
        )
    )

    assert "INSERT INTO backtest_runs" in pipeline_sources
    assert "strategy_version" in pipeline_sources
    assert "parameters" in pipeline_sources
    assert "metrics" in pipeline_sources


def test_wave_e_retirement_keeps_only_the_safe_readiness_entry_point() -> None:
    retired = (
        ROOT / "scripts" / "migrate_sqlite_to_postgres.py",
        ROOT / "scripts" / "report_analysis_summary.py",
        ROOT / "scripts" / "update_asset_quality_scores.py",
        ROOT / "scripts" / "validate_db.py",
        ROOT / "services" / "import_excel.py",
    )

    assert all(not path.exists() for path in retired)
    assert (ROOT / "scripts" / "production_readiness_check.py").is_file()
