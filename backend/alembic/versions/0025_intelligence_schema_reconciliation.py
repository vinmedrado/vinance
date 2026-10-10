"""reconcile Intelligence ML feature tables with canonical metadata

Revision ID: 0025_intelligence_schema
Revises: 0024_household_product_v1
Create Date: 2026-10-09

Migration 0006 created a generic historical shape for the five Intelligence
feature tables.  The canonical database later evolved with the market-specific
models, but that evolution was never represented in Alembic.  This migration is
therefore deliberately introspection-driven: a fresh database is upgraded from
the 0006 shape, while an already-canonical database is left structurally
unchanged.

The downgrade removes market-specific columns and changes numeric precision.
It is consequently allowed only while all five tables are empty.  Alembic will
fail closed instead of silently destroying feature history.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0025_intelligence_schema"
down_revision = "0024_household_product_v1"
branch_labels = None
depends_on = None


TICKER_FEATURE_TABLES: dict[str, tuple[str, ...]] = {
    "acoes_ml_features": (
        "pl_zscore",
        "roe_trend_3m",
        "momentum_252d",
        "volatilidade_90d",
        "retorno_vs_ibov",
        "volume_anomaly",
    ),
    "bdr_ml_features": (
        "cambio_trend_30d",
        "retorno_vs_spy",
        "liquidez_score",
    ),
    "etf_ml_features": (
        "taxa_adm_rank",
        "tracking_score",
        "retorno_vs_benchmark",
    ),
    "fii_ml_features": (
        "dy_trend_3m",
        "pvp_zscore",
        "vacancia_delta",
        "retorno_vs_ifix",
    ),
}

CRYPTO_EXTRA_COLUMNS = (
    "volatilidade_7d",
    "correlacao_btc_30d",
    "momentum_7d",
    "volume_anomaly",
    "fear_greed_score",
)

ALL_FEATURE_TABLES = (*TICKER_FEATURE_TABLES, "cripto_ml_features")
COMMON_FEATURE_COLUMNS = ("momentum_30d", "momentum_90d", "volatilidade_30d")


def _inspector() -> sa.Inspector:
    # A new inspector is intentional: PostgreSQL reflection is cached, while
    # this migration adds and removes objects in several consecutive steps.
    return sa.inspect(op.get_bind())


def _columns(table_name: str) -> dict[str, dict]:
    return {column["name"]: column for column in _inspector().get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    return {index["name"] for index in _inspector().get_indexes(table_name)}


def _unique_names(table_name: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in _inspector().get_unique_constraints(table_name)
        if constraint.get("name")
    }


def _is_numeric(type_: sa.types.TypeEngine, precision: int, scale: int) -> bool:
    return (
        isinstance(type_, sa.Numeric)
        and type_.precision == precision
        and type_.scale == scale
    )


def _add_numeric_columns(table_name: str, column_names: tuple[str, ...]) -> None:
    existing = _columns(table_name)
    for column_name in column_names:
        if column_name not in existing:
            op.add_column(
                table_name,
                sa.Column(column_name, sa.Numeric(18, 6), nullable=True),
            )


def _ensure_numeric(
    table_name: str,
    column_name: str,
    *,
    precision: int,
    scale: int,
) -> None:
    column = _columns(table_name)[column_name]
    existing_type = column["type"]
    if _is_numeric(existing_type, precision, scale):
        return
    op.alter_column(
        table_name,
        column_name,
        existing_type=existing_type,
        existing_nullable=column["nullable"],
        type_=sa.Numeric(precision, scale),
        postgresql_using=f'"{column_name}"::numeric({precision},{scale})',
    )


def _ensure_float(table_name: str, column_name: str) -> None:
    column = _columns(table_name)[column_name]
    existing_type = column["type"]
    if isinstance(existing_type, sa.Float) and not isinstance(existing_type, sa.Numeric):
        return
    op.alter_column(
        table_name,
        column_name,
        existing_type=existing_type,
        existing_nullable=column["nullable"],
        type_=sa.Float(),
        postgresql_using=f'"{column_name}"::double precision',
    )


def _drop_index_if_present(table_name: str, index_name: str) -> None:
    if index_name in _index_names(table_name):
        op.drop_index(index_name, table_name=table_name)


def _create_index_if_missing(
    table_name: str,
    index_name: str,
    column_names: list[str],
) -> None:
    if index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, column_names, unique=False)


def _reconcile_common_numeric_columns(table_name: str) -> None:
    for column_name in COMMON_FEATURE_COLUMNS:
        _ensure_numeric(table_name, column_name, precision=18, scale=6)
    _ensure_numeric(table_name, "score_final", precision=10, scale=6)


def _replace_legacy_indexes(table_name: str) -> None:
    _drop_index_if_present(table_name, f"ix_{table_name}_ticker")
    _drop_index_if_present(table_name, f"ix_{table_name}_date")
    _create_index_if_missing(table_name, f"ix_{table_name}_id", ["id"])
    _create_index_if_missing(
        table_name,
        f"ix_{table_name}_score_final",
        ["score_final"],
    )
    _create_index_if_missing(
        table_name,
        f"ix_{table_name}_ticker_date",
        ["ticker", "date"],
    )


def _backfill_crypto_coin_id() -> None:
    columns = _columns("cripto_ml_features")
    if "coin_id" not in columns:
        op.add_column(
            "cripto_ml_features",
            sa.Column("coin_id", sa.String(120), nullable=True),
        )
    else:
        coin_type = columns["coin_id"]["type"]
        if not isinstance(coin_type, sa.String) or coin_type.length != 120:
            op.alter_column(
                "cripto_ml_features",
                "coin_id",
                existing_type=coin_type,
                existing_nullable=columns["coin_id"]["nullable"],
                type_=sa.String(120),
                postgresql_using='"coin_id"::varchar(120)',
            )

    # The historical schema knows only ticker.  Prefixing the normalized value
    # makes the provenance explicit and preserves a stable identifier across
    # dates without pretending it is a provider-native coin id.
    op.execute(
        sa.text(
            """
            UPDATE cripto_ml_features
               SET coin_id = 'legacy:' || lower(btrim(ticker))
             WHERE coin_id IS NULL
            """
        )
    )

    duplicate = op.get_bind().execute(
        sa.text(
            """
            SELECT coin_id, date
              FROM cripto_ml_features
             GROUP BY coin_id, date
            HAVING count(*) > 1
             LIMIT 1
            """
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot reconcile cripto_ml_features: duplicate coin_id/date "
            f"would violate the canonical constraint ({duplicate[0]!r}, {duplicate[1]!r})."
        )

    column = _columns("cripto_ml_features")["coin_id"]
    if column["nullable"]:
        op.alter_column(
            "cripto_ml_features",
            "coin_id",
            existing_type=sa.String(120),
            existing_nullable=True,
            nullable=False,
        )


def _reconcile_crypto_constraints() -> None:
    legacy_name = "uq_cripto_ml_features_ticker_date"
    canonical_name = "uq_cripto_ml_features_coin_id_date"
    unique_names = _unique_names("cripto_ml_features")
    if legacy_name in unique_names:
        op.drop_constraint(legacy_name, "cripto_ml_features", type_="unique")
    if canonical_name not in _unique_names("cripto_ml_features"):
        op.create_unique_constraint(
            canonical_name,
            "cripto_ml_features",
            ["coin_id", "date"],
        )


def upgrade() -> None:
    for table_name, extra_columns in TICKER_FEATURE_TABLES.items():
        _add_numeric_columns(table_name, extra_columns)
        _reconcile_common_numeric_columns(table_name)
        _replace_legacy_indexes(table_name)

    _backfill_crypto_coin_id()
    _add_numeric_columns("cripto_ml_features", CRYPTO_EXTRA_COLUMNS)
    _reconcile_common_numeric_columns("cripto_ml_features")
    _reconcile_crypto_constraints()
    _replace_legacy_indexes("cripto_ml_features")
    _create_index_if_missing(
        "cripto_ml_features",
        "ix_cripto_ml_features_coin_id_date",
        ["coin_id", "date"],
    )


def _assert_feature_tables_empty_for_downgrade() -> None:
    populated: list[str] = []
    bind = op.get_bind()
    for table_name in ALL_FEATURE_TABLES:
        count = bind.execute(
            sa.text(f'SELECT count(*) FROM "{table_name}"')
        ).scalar_one()
        if count:
            populated.append(f"{table_name}={count}")
    if populated:
        raise RuntimeError(
            "Downgrade to 0024 would discard canonical Intelligence columns and "
            "precision. It is permitted only when all five feature tables are "
            f"empty; populated tables: {', '.join(populated)}"
        )


def _restore_legacy_indexes(table_name: str) -> None:
    _drop_index_if_present(table_name, f"ix_{table_name}_ticker_date")
    _drop_index_if_present(table_name, f"ix_{table_name}_score_final")
    _drop_index_if_present(table_name, f"ix_{table_name}_id")
    _create_index_if_missing(table_name, f"ix_{table_name}_ticker", ["ticker"])
    _create_index_if_missing(table_name, f"ix_{table_name}_date", ["date"])


def _drop_columns_if_present(table_name: str, column_names: tuple[str, ...]) -> None:
    existing = _columns(table_name)
    for column_name in column_names:
        if column_name in existing:
            op.drop_column(table_name, column_name)


def _restore_legacy_common_types(table_name: str) -> None:
    for column_name in (*COMMON_FEATURE_COLUMNS, "score_final"):
        _ensure_float(table_name, column_name)


def downgrade() -> None:
    _assert_feature_tables_empty_for_downgrade()

    _drop_index_if_present(
        "cripto_ml_features",
        "ix_cripto_ml_features_coin_id_date",
    )
    canonical_unique = "uq_cripto_ml_features_coin_id_date"
    if canonical_unique in _unique_names("cripto_ml_features"):
        op.drop_constraint(canonical_unique, "cripto_ml_features", type_="unique")
    legacy_unique = "uq_cripto_ml_features_ticker_date"
    if legacy_unique not in _unique_names("cripto_ml_features"):
        op.create_unique_constraint(
            legacy_unique,
            "cripto_ml_features",
            ["ticker", "date"],
        )

    _restore_legacy_indexes("cripto_ml_features")
    _drop_columns_if_present(
        "cripto_ml_features",
        ("coin_id", *CRYPTO_EXTRA_COLUMNS),
    )
    _restore_legacy_common_types("cripto_ml_features")

    for table_name, extra_columns in reversed(tuple(TICKER_FEATURE_TABLES.items())):
        _restore_legacy_indexes(table_name)
        _drop_columns_if_present(table_name, extra_columns)
        _restore_legacy_common_types(table_name)
