from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RETIRED_IMPORT_FRAGMENTS = ("db" + ".database", "backend.app" + ".database")

RETIRED_PATHS = (
    ROOT / "backend" / "app" / "database.py",
    ROOT / "backend" / "app" / "billing" / "stripe_router.py",
    ROOT / "backend" / "app" / "enterprise" / "context.py",
    ROOT / "backend" / "app" / "enterprise" / "models.py",
    ROOT / "backend" / "app" / "enterprise" / "router.py",
    ROOT / "backend" / "app" / "erp" / "models.py",
    ROOT / "backend" / "app" / "erp" / "router.py",
    ROOT / "backend" / "app" / "erp" / "service.py",
    ROOT / "backend" / "app" / "financial" / "routers" / "financial.py",
    ROOT / "backend" / "app" / "financing" / "models.py",
    ROOT / "backend" / "app" / "financing" / "routers" / "__init__.py",
    ROOT / "backend" / "app" / "financing" / "routers" / "financing.py",
    ROOT / "backend" / "app" / "intelligence" / "financial_context_builder.py",
    ROOT / "backend" / "app" / "intelligence" / "models.py",
    ROOT / "backend" / "app" / "intelligence" / "user_learning_profile_service.py",
    ROOT / "backend" / "app" / "investment" / "models.py",
    ROOT / "backend" / "app" / "investment" / "routers" / "investment.py",
    ROOT / "backend" / "app" / "investment" / "services" / "analysis_service.py",
    ROOT / "backend" / "app" / "investment" / "services" / "data_sync_service.py",
    ROOT / "backend" / "app" / "market" / "jobs.py",
    ROOT / "backend" / "app" / "market" / "models.py",
    ROOT / "backend" / "app" / "market" / "services" / "market_data_service.py",
    ROOT / "backend" / "app" / "market" / "services" / "radar_service.py",
    ROOT / "backend" / "app" / "models" / "__init__.py",
    ROOT / "services" / "investor_service.py",
    ROOT / "services" / "portfolio_service.py",
)


def test_dormant_database_island_is_physically_retired() -> None:
    assert all(not path.exists() for path in RETIRED_PATHS)


def test_product_sources_do_not_reference_retired_database_modules() -> None:
    violations: list[str] = []
    for source_root in (ROOT / "backend", ROOT / "services", ROOT / "workers", ROOT / "scripts"):
        for path in source_root.rglob("*.py"):
            if {"__pycache__", "tests"} & set(path.parts):
                continue
            source = path.read_text(encoding="utf-8", errors="ignore")
            if any(fragment in source for fragment in RETIRED_IMPORT_FRAGMENTS):
                violations.append(path.relative_to(ROOT).as_posix())
    assert violations == []


def test_canonical_components_needed_after_retirement_remain_present() -> None:
    preserved = (
        ROOT / "backend" / "app" / "core" / "database.py",
        ROOT / "backend" / "app" / "financing" / "schemas.py",
        ROOT / "backend" / "app" / "financing" / "services" / "calculator.py",
        ROOT / "backend" / "app" / "investment" / "portfolio_allocator.py",
        ROOT / "backend" / "app" / "investment" / "engines" / "__init__.py",
        ROOT / "backend" / "app" / "market" / "models" / "__init__.py",
        ROOT / "backend" / "app" / "intelligence" / "models" / "__init__.py",
    )
    assert all(path.is_file() for path in preserved)
