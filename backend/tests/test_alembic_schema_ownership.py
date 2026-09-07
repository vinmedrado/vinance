from __future__ import annotations

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


def test_ml_feature_tables_belong_to_main_alembic_metadata() -> None:
    assert ML_FEATURE_TABLES.issubset(Base.metadata.tables)


def test_trading_v2_explicit_schema_is_external_to_main_alembic() -> None:
    assert TRADING_EXTERNAL_TABLES.isdisjoint(Base.metadata.tables)
    assert all(not include_name(table, "table", {}) for table in TRADING_EXTERNAL_TABLES)
    assert include_name("users", "table", {})
