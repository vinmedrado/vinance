from __future__ import annotations

import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


RETIRED_PATHS = (
    ROOT / "backend" / "app" / "auth" / "schema.py",
    ROOT / "backend" / "app" / "core" / "pg_compat.py",
    ROOT / "backend" / "app" / "models.py",
    ROOT / "services" / "background_jobs.py",
    ROOT / "services" / "automation_service.py",
    ROOT / "services" / "job_executor.py",
    ROOT / "services" / "alert_engine.py",
    ROOT / "workers" / "tasks.py",
    ROOT / "workers" / "celery_app.py",
    ROOT / "scripts" / "scheduler.py",
    ROOT / "scripts" / "smoke_vinance.py",
    ROOT / "scripts" / "migrate_sqlite_to_postgres.py",
    ROOT / "services" / "import_excel.py",
)


def _product_python_sources() -> list[Path]:
    roots = (ROOT / "backend" / "app", ROOT / "services", ROOT / "workers", ROOT / "scripts")
    sources: list[Path] = []
    for source_root in roots:
        if not source_root.exists():
            continue
        for path in source_root.rglob("*.py"):
            if {"__pycache__", "tests", "_legacy"} & set(path.parts):
                continue
            sources.append(path)
    return sources


def test_retired_sqlite_and_background_entry_points_are_absent() -> None:
    assert all(not path.exists() for path in RETIRED_PATHS)


def test_product_sources_have_no_executable_sqlite_compatibility() -> None:
    forbidden = ("pg_compat", "sqlite3", "sqlite+aiosqlite", "sqlite_master", "PRAGMA")
    violations = []
    for path in _product_python_sources():
        source = path.read_text(encoding="utf-8", errors="ignore")
        if any(token in source for token in forbidden):
            violations.append(path.relative_to(ROOT).as_posix())
    assert violations == []


def test_canonical_runtime_has_no_manual_schema_ddl_or_legacy_workers() -> None:
    runtime_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "backend" / "app" / "main.py",
            ROOT / "backend" / "app" / "api" / "v1" / "router.py",
            ROOT / "backend" / "app" / "core" / "celery.py",
        )
    )
    forbidden = (
        "CREATE TABLE",
        "ALTER TABLE",
        "DROP TABLE",
        "CREATE INDEX",
        "workers.tasks",
        "workers.celery_app",
    )
    assert all(token not in runtime_sources for token in forbidden)


def test_deployment_uses_the_canonical_celery_application() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    canonical = "backend.app.core.celery.celery_app"
    assert canonical in compose
    assert canonical in render
    assert "workers.celery_app" not in compose
    assert "workers.celery_app" not in render


def test_production_health_uses_canonical_authentication() -> None:
    source = (ROOT / "services" / "production_health_service.py").read_text(encoding="utf-8")

    assert "backend.app.auth.dependencies" in source
    assert "services.auth_middleware" not in source


def test_readiness_tool_import_is_side_effect_free(monkeypatch) -> None:
    from backend.app.core import sync_database

    def fail_if_session_is_created():
        raise AssertionError("readiness import must not open a database session")

    monkeypatch.setattr(sync_database, "create_sync_session", fail_if_session_is_created)
    sys.modules.pop("scripts.production_readiness_check", None)
    module = importlib.import_module("scripts.production_readiness_check")
    assert callable(module.main)


def test_readiness_source_scanner_reports_no_runtime_sqlite() -> None:
    from services.production_health_service import check_sqlite_disabled

    result = check_sqlite_disabled()
    assert result["status"] == "pass"
    assert result["details"] == {}


def test_trading_v2_stack_remains_present() -> None:
    preserved = (
        ROOT / "backend" / "trading" / "feature_store" / "__init__.py",
        ROOT / "backend" / "trading" / "target_engine" / "__init__.py",
        ROOT / "backend" / "trading" / "ml_engine" / "__init__.py",
        ROOT / "backend" / "trading" / "prediction_engine" / "__init__.py",
        ROOT / "backend" / "trading" / "backtesting_v2" / "__init__.py",
        ROOT / "backend" / "trading" / "research_v2" / "__init__.py",
        ROOT / "backend" / "trading" / "validation_v2" / "__init__.py",
    )
    assert all(path.is_file() for path in preserved)
