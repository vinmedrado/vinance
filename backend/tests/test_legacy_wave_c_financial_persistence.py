from __future__ import annotations

from pathlib import Path

from backend.app.financial.models import Expense, FinancialProfile, Income
from backend.app.financial.services.financial_analysis import (
    get_financial_capacity,
    get_financial_summary,
)


ROOT = Path(__file__).resolve().parents[2]


def test_obsolete_financial_sqlite_paths_are_retired() -> None:
    retired_paths = (
        ROOT / "services" / "despesas.py",
        ROOT / "services" / "financial_crud_service.py",
        ROOT / "services" / "erp_finance_service.py",
        ROOT / "services" / "financial_intelligence_service.py",
        ROOT / "backend" / "app" / "core" / "services" / "personal_finance.py",
        ROOT / "backend" / "app" / "core" / "routers" / "core.py",
    )

    assert all(not path.exists() for path in retired_paths)


def test_canonical_financial_models_enforce_user_ownership() -> None:
    for model in (Income, Expense, FinancialProfile):
        user_id = model.__table__.c.user_id
        assert not user_id.nullable
        assert {foreign_key.target_fullname for foreign_key in user_id.foreign_keys} == {"users.id"}

    assert FinancialProfile.__table__.c.user_id.unique


def test_legacy_analysis_accepts_only_explicit_owner_scoped_values() -> None:
    summary = get_financial_summary(
        renda_mensal=6000,
        despesas_mensais=2400,
        despesas_pendentes=900,
        despesas_pagas=1500,
    )
    capacity = get_financial_capacity(
        renda_mensal=6000,
        despesas_mensais=2400,
    )

    assert summary["renda_total"] == 6000
    assert summary["despesas_totais"] == 2400
    assert summary["saldo_mensal"] == 3600
    assert summary["fonte"] == "explicit_owner_scoped_input"
    assert summary["core"] == {}
    assert capacity["capacidade_segura"] == 1500


def test_wave_c_paths_have_no_implicit_sqlite_or_demo_owner() -> None:
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "backend" / "app" / "financial" / "models.py",
            ROOT / "backend" / "app" / "financial" / "service.py",
            ROOT / "backend" / "app" / "financial" / "router.py",
            ROOT / "backend" / "app" / "financial" / "services" / "financial_analysis.py",
            ROOT / "backend" / "app" / "financing" / "routers" / "financing.py",
        )
    )

    assert "sqlite3" not in sources
    assert "sqlite_master" not in sources
    assert "PRAGMA" not in sources
    assert "demo-user" not in sources
    assert "pg_compat" not in sources
    assert "personal_finance" not in sources


def test_legacy_excel_importer_is_retired_from_official_runtime() -> None:
    importer = ROOT / "services" / "import_excel.py"
    runtime_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "backend" / "app" / "main.py",
            ROOT / "backend" / "app" / "api" / "v1" / "router.py",
            ROOT / "backend" / "app" / "core" / "celery.py",
        )
    )

    assert not importer.exists()
    assert "services.import_excel" not in runtime_sources
    assert "import_excel" not in runtime_sources


def test_wave_c_product_gaps_are_explicitly_documented() -> None:
    report = (ROOT / "docs" / "LEGACY_WAVE_C_FINANCIAL_PERSISTENCE.md").read_text(encoding="utf-8")

    assert "PRODUCT_GAP_PORTFOLIO" in report
    assert "PRODUCT_GAP_GOALS" in report
    assert "PRODUCT_GAP_HOUSEHOLD" in report
    assert "OWNERSHIP_MAPPING_REQUIRED" in report
