from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from backend.alembic.schema_ownership import TRADING_EXTERNAL_TABLES, include_name
from backend.app.core.database import Base
from backend.app.intelligence.models import (  # noqa: F401
    AcaoMLFeature,
    BdrMLFeature,
    CriptoMLFeature,
    EtfMLFeature,
    FiiMLFeature,
)


ML_FEATURE_TABLES = {
    "acoes_ml_features",
    "bdr_ml_features",
    "cripto_ml_features",
    "etf_ml_features",
    "fii_ml_features",
}

ROOT = Path(__file__).resolve().parents[2]

EXPECTED_MARKET_COLUMNS = {
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


def test_ml_feature_tables_belong_to_main_alembic_metadata() -> None:
    assert ML_FEATURE_TABLES.issubset(Base.metadata.tables)


def test_ml_feature_metadata_keeps_market_specific_contracts() -> None:
    for table_name, expected_columns in EXPECTED_MARKET_COLUMNS.items():
        table = Base.metadata.tables[table_name]
        assert expected_columns.issubset(table.columns.keys())
        for common_name in (
            "momentum_30d",
            "momentum_90d",
            "volatilidade_30d",
        ):
            common_type = table.columns[common_name].type
            assert (common_type.precision, common_type.scale) == (18, 6)
        score_type = table.columns["score_final"].type
        assert (score_type.precision, score_type.scale) == (10, 6)


def test_alembic_graph_has_one_resolvable_head() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0025_intelligence_schema"]
    revisions = list(script.walk_revisions())
    assert revisions[-1].down_revision is None
    assert len({revision.revision for revision in revisions}) == len(revisions)


def test_trading_v2_explicit_schema_is_external_to_main_alembic() -> None:
    assert TRADING_EXTERNAL_TABLES.isdisjoint(Base.metadata.tables)
    assert all(not include_name(table, "table", {}) for table in TRADING_EXTERNAL_TABLES)
    assert include_name("users", "table", {})
