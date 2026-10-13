from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[2]
FRESH_DATABASE_URL = os.getenv("ALEMBIC_FRESH_TEST_DATABASE_URL")

INTELLIGENCE_COLUMNS = {
    "acoes_ml_features": {
        "pl_zscore",
        "roe_trend_3m",
        "momentum_252d",
        "volatilidade_90d",
        "retorno_vs_ibov",
        "volume_anomaly",
    },
    "bdr_ml_features": {
        "cambio_trend_30d",
        "retorno_vs_spy",
        "liquidez_score",
    },
    "cripto_ml_features": {
        "coin_id",
        "volatilidade_7d",
        "correlacao_btc_30d",
        "momentum_7d",
        "volume_anomaly",
        "fear_greed_score",
    },
    "etf_ml_features": {
        "taxa_adm_rank",
        "tracking_score",
        "retorno_vs_benchmark",
    },
    "fii_ml_features": {
        "dy_trend_3m",
        "pvp_zscore",
        "vacancia_delta",
        "retorno_vs_ifix",
    },
}

FIXED_INCOME_COLUMNS = {
    "source_product_id",
    "asset_catalog_id",
    "nome",
    "emissor",
    "tipo",
    "indexador",
    "rate_type",
    "purchase_rate",
    "redemption_rate",
    "unit_price",
    "redemption_unit_price",
    "base_unit_price",
    "vencimento",
    "liquidez_dias",
    "liquidity_type",
    "investimento_minimo",
    "guarantee_type",
    "tax_treatment",
    "currency",
    "market_date",
    "source_metadata",
    "source",
    "coletado_em",
    "is_active",
}

TRADING_EXTERNAL_TABLES = {
    "backtest_runs",
    "crypto_candles",
    "crypto_features",
    "crypto_targets",
    "paper_trades",
    "trading_signals",
}


def _run_alembic(*arguments: str, database_url: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def _sync_url(database_url: str) -> str:
    url = make_url(database_url)
    return url.set(drivername="postgresql+psycopg2").render_as_string(
        hide_password=False
    )


@pytest.mark.skipif(
    not FRESH_DATABASE_URL,
    reason=(
        "set ALEMBIC_FRESH_TEST_DATABASE_URL to a dedicated empty PostgreSQL "
        "database; this test rebuilds its public schema"
    ),
)
def test_fresh_alembic_database_matches_canonical_metadata() -> None:
    """Prove that Alembic alone can reproduce the canonical application schema."""

    assert FRESH_DATABASE_URL is not None
    database_name = (make_url(FRESH_DATABASE_URL).database or "").lower()
    assert "test" in database_name
    assert database_name != "vinance"

    engine = sa.create_engine(_sync_url(FRESH_DATABASE_URL))
    try:
        with engine.begin() as connection:
            connection.execute(sa.text("DROP SCHEMA public CASCADE"))
            connection.execute(sa.text("CREATE SCHEMA public"))
    finally:
        engine.dispose()

    upgrade = _run_alembic("upgrade", "head", database_url=FRESH_DATABASE_URL)
    assert upgrade.returncode == 0, upgrade.stdout + upgrade.stderr

    current = _run_alembic("current", database_url=FRESH_DATABASE_URL)
    assert current.returncode == 0, current.stdout + current.stderr
    assert "0027_auth_sessions (head)" in current.stdout

    check = _run_alembic("check", database_url=FRESH_DATABASE_URL)
    assert check.returncode == 0, check.stdout + check.stderr
    assert "No new upgrade operations detected." in check.stdout

    engine = sa.create_engine(_sync_url(FRESH_DATABASE_URL))
    try:
        inspector = sa.inspect(engine)
        table_names = set(inspector.get_table_names())
        assert not (TRADING_EXTERNAL_TABLES & table_names)
        for table_name, expected_columns in INTELLIGENCE_COLUMNS.items():
            assert table_name in table_names
            actual_columns = {
                column["name"]: column
                for column in inspector.get_columns(table_name)
            }
            assert expected_columns.issubset(actual_columns)

            for common_name in (
                "momentum_30d",
                "momentum_90d",
                "volatilidade_30d",
            ):
                common_type = actual_columns[common_name]["type"]
                assert isinstance(common_type, sa.Numeric)
                assert (common_type.precision, common_type.scale) == (18, 6)

            score_type = actual_columns["score_final"]["type"]
            assert isinstance(score_type, sa.Numeric)
            assert (score_type.precision, score_type.scale) == (10, 6)

            index_names = {
                index["name"] for index in inspector.get_indexes(table_name)
            }
            assert f"ix_{table_name}_id" in index_names
            assert f"ix_{table_name}_score_final" in index_names
            assert f"ix_{table_name}_ticker_date" in index_names

        crypto_columns = {
            column["name"]: column
            for column in inspector.get_columns("cripto_ml_features")
        }
        assert crypto_columns["coin_id"]["nullable"] is False
        crypto_uniques = {
            unique["name"]: tuple(unique["column_names"])
            for unique in inspector.get_unique_constraints("cripto_ml_features")
        }
        assert crypto_uniques["uq_cripto_ml_features_coin_id_date"] == (
            "coin_id",
            "date",
        )

        fixed_income_columns = {
            column["name"]: column
            for column in inspector.get_columns("renda_fixa_produtos")
        }
        assert FIXED_INCOME_COLUMNS.issubset(fixed_income_columns)
        assert fixed_income_columns["source_product_id"]["nullable"] is False
        assert fixed_income_columns["currency"]["nullable"] is False

        fixed_income_uniques = {
            unique["name"]: tuple(unique["column_names"])
            for unique in inspector.get_unique_constraints("renda_fixa_produtos")
        }
        assert fixed_income_uniques["uq_renda_fixa_produtos_source_product"] == (
            "source",
            "source_product_id",
        )

        fixed_income_indexes = {
            index["name"] for index in inspector.get_indexes("renda_fixa_produtos")
        }
        assert {
            "ix_renda_fixa_produtos_asset_catalog_id",
            "ix_renda_fixa_produtos_market_date",
            "ix_renda_fixa_produtos_active_market_date",
        }.issubset(fixed_income_indexes)

        profile_columns = {
            column["name"]: column
            for column in inspector.get_columns("financial_profiles")
        }
        assert profile_columns["investment_horizon_months"]["nullable"] is True
    finally:
        engine.dispose()
