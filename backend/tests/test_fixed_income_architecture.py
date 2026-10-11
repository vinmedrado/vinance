from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_only_canonical_modules_own_fixed_income_rules_and_ingestion() -> None:
    old_engine = (
        ROOT / "backend/app/investment/engines/fixed_income_engine.py"
    ).read_text(encoding="utf-8-sig")
    old_lci = (
        ROOT / "backend/app/investment/engines/lci_lca_engine.py"
    ).read_text(encoding="utf-8-sig")
    old_provider = (
        ROOT / "backend/app/investment/data_sources/tesouro_provider.py"
    ).read_text(encoding="utf-8-sig")
    old_importer = (
        ROOT / "backend/app/investment/data_sources/csv_importer.py"
    ).read_text(encoding="utf-8-sig")

    assert "class FixedIncomeEngine" not in old_engine
    assert "class LCILCAEngine" not in old_lci
    assert "treasurybondsinfo.json" not in old_provider
    assert "class FixedIncomeCSVImporter" not in old_importer
    assert "backend.app.fixed_income.engine" in old_engine
    assert "backend.app.market.providers.tesouro" in old_provider


def test_crypto_and_private_fixed_income_are_not_falsely_enabled() -> None:
    docs = (ROOT / "docs/FIXED_INCOME_V1.md").read_text(encoding="utf-8-sig")
    assert "CDB, LCI and LCA are not supported" in docs
    assert "Crypto investment also remains unsupported" in docs


def test_fixed_income_migration_owns_only_canonical_application_schema() -> None:
    migration = (
        ROOT / "backend/alembic/versions/0026_fixed_income_v1.py"
    ).read_text(encoding="utf-8-sig")

    assert 'revision = "0026_fixed_income_v1"' in migration
    assert 'down_revision = "0025_intelligence_schema"' in migration
    assert "renda_fixa_produtos" in migration
    assert "investment_horizon_months" in migration
    for external_table in (
        "backtest_runs",
        "crypto_candles",
        "crypto_features",
        "crypto_targets",
        "paper_trades",
        "trading_signals",
    ):
        assert external_table not in migration
