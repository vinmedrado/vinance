from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


# ============================================================
# CONFIGURAÇÕES
# ============================================================

SCHEMA = os.getenv("AUDIT_SCHEMA", "public")

# Quantidade máxima de linhas usada nas análises estatísticas.
SAMPLE_SIZE = int(os.getenv("AUDIT_SAMPLE_SIZE", "10000"))

# Quantidade de linhas exportadas por tabela.
EXPORT_SAMPLE_SIZE = int(os.getenv("AUDIT_EXPORT_SIZE", "5000"))

# Evita auditar tabelas internas ou tabelas irrelevantes.
IGNORED_TABLES = {
    "alembic_version",
    "django_migrations",
    "django_content_type",
    "django_admin_log",
    "auth_permission",
    "auth_group",
    "auth_group_permissions",
    "auth_user",
    "auth_user_groups",
    "auth_user_user_permissions",
}

# Palavras que ajudam a identificar tabelas de mercado.
MARKET_TABLE_KEYWORDS = {
    "candle",
    "candles",
    "kline",
    "klines",
    "price",
    "prices",
    "market",
    "ticker",
    "quote",
    "trade",
    "trades",
    "crypto",
    "asset",
    "ohlcv",
}

# Possíveis nomes de colunas temporais.
TIME_COLUMN_CANDIDATES = [
    "timestamp",
    "datetime",
    "date_time",
    "open_time",
    "close_time",
    "created_at",
    "updated_at",
    "collected_at",
    "recorded_at",
    "time",
    "date",
]

# Possíveis identificadores de ativos.
SYMBOL_COLUMN_CANDIDATES = [
    "symbol",
    "ticker",
    "asset",
    "asset_symbol",
    "pair",
    "market",
    "coin",
    "currency",
]

OUTPUT_DIR = Path(
    os.getenv(
        "AUDIT_OUTPUT_DIR",
        f"auditoria_vinance_{datetime.now():%Y%m%d_%H%M%S}",
    )
)


# ============================================================
# FUNÇÕES UTILITÁRIAS
# ============================================================

def get_database_url() -> str:
    """
    Busca a URL do banco em variáveis de ambiente comuns.
    """

    candidates = [
        "DATABASE_URL",
        "POSTGRES_URL",
        "SQLALCHEMY_DATABASE_URI",
    ]

    for variable_name in candidates:
        value = os.getenv(variable_name)

        if value:
            # Corrige formato antigo usado por algumas plataformas.
            if value.startswith("postgres://"):
                value = value.replace(
                    "postgres://",
                    "postgresql://",
                    1,
                )

            return value

    # Monta a URL com variáveis separadas, caso DATABASE_URL não exista.
    host = os.getenv("POSTGRES_HOST") or os.getenv("DB_HOST")
    port = os.getenv("POSTGRES_PORT") or os.getenv("DB_PORT", "5432")
    database = (
        os.getenv("POSTGRES_DB")
        or os.getenv("DB_NAME")
        or os.getenv("DATABASE_NAME")
    )
    user = (
        os.getenv("POSTGRES_USER")
        or os.getenv("DB_USER")
        or os.getenv("DATABASE_USER")
    )
    password = (
        os.getenv("POSTGRES_PASSWORD")
        or os.getenv("DB_PASSWORD")
        or os.getenv("DATABASE_PASSWORD")
    )

    if all([host, database, user, password]):
        return (
            f"postgresql+psycopg2://"
            f"{user}:{password}@{host}:{port}/{database}"
        )

    raise RuntimeError(
        "Não encontrei a conexão do banco.\n"
        "Defina DATABASE_URL ou as variáveis:\n"
        "POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, "
        "POSTGRES_USER e POSTGRES_PASSWORD."
    )


def safe_identifier(identifier: str) -> str:
    """
    Valida nomes de tabelas, schemas e colunas usados nas consultas.
    """

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
        raise ValueError(f"Identificador SQL inválido: {identifier}")

    return identifier


def serialize_value(value: Any) -> Any:
    """
    Converte valores não serializáveis para JSON.
    """

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, datetime):
        return value.isoformat()

    return str(value)


def create_database_engine() -> Engine:
    database_url = get_database_url()

    database_url = database_url.replace(
        "postgresql+asyncpg://",
        "postgresql+psycopg2://",
        1,
    )

    database_url = database_url.replace(
        "postgresql+psycopg://",
        "postgresql+psycopg2://",
        1,
    )

    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=300,
    )

def execute_scalar(
    engine: Engine,
    query: str,
    parameters: dict[str, Any] | None = None,
) -> Any:
    with engine.connect() as connection:
        result = connection.execute(
            text(query),
            parameters or {},
        )

        return result.scalar()


def find_column(
    available_columns: list[str],
    candidates: list[str],
) -> str | None:
    normalized = {
        column.lower(): column
        for column in available_columns
    }

    for candidate in candidates:
        if candidate.lower() in normalized:
            return normalized[candidate.lower()]

    return None


# ============================================================
# AUDITORIA GERAL
# ============================================================

def get_database_information(engine: Engine) -> dict[str, Any]:
    query = """
        SELECT
            current_database() AS database_name,
            current_user AS database_user,
            version() AS postgres_version,
            pg_size_pretty(
                pg_database_size(current_database())
            ) AS database_size,
            pg_database_size(
                current_database()
            ) AS database_size_bytes;
    """

    dataframe = pd.read_sql(text(query), engine)

    if dataframe.empty:
        return {}

    return {
        key: serialize_value(value)
        for key, value in dataframe.iloc[0].to_dict().items()
    }


def get_table_statistics(engine: Engine) -> pd.DataFrame:
    """
    Obtém quantidade aproximada de linhas e tamanho físico das tabelas.

    Usa estatísticas do PostgreSQL para evitar COUNT(*) em todas as tabelas.
    """

    query = """
        SELECT
            schemaname AS schema_name,
            relname AS table_name,
            n_live_tup::bigint AS estimated_rows,
            n_dead_tup::bigint AS estimated_dead_rows,
            pg_total_relation_size(
                quote_ident(schemaname) || '.' || quote_ident(relname)
            ) AS total_size_bytes,
            pg_size_pretty(
                pg_total_relation_size(
                    quote_ident(schemaname) || '.' || quote_ident(relname)
                )
            ) AS total_size,
            pg_size_pretty(
                pg_relation_size(
                    quote_ident(schemaname) || '.' || quote_ident(relname)
                )
            ) AS table_size,
            pg_size_pretty(
                pg_indexes_size(
                    quote_ident(schemaname) || '.' || quote_ident(relname)
                )
            ) AS indexes_size,
            last_analyze,
            last_autoanalyze,
            last_vacuum,
            last_autovacuum
        FROM pg_stat_user_tables
        WHERE schemaname = :schema
        ORDER BY total_size_bytes DESC;
    """

    return pd.read_sql(
        text(query),
        engine,
        params={"schema": SCHEMA},
    )


def get_indexes(engine: Engine) -> pd.DataFrame:
    query = """
        SELECT
            schemaname AS schema_name,
            tablename AS table_name,
            indexname AS index_name,
            indexdef AS index_definition
        FROM pg_indexes
        WHERE schemaname = :schema
        ORDER BY tablename, indexname;
    """

    return pd.read_sql(
        text(query),
        engine,
        params={"schema": SCHEMA},
    )


def get_constraints(engine: Engine) -> pd.DataFrame:
    query = """
        SELECT
            tc.table_schema,
            tc.table_name,
            tc.constraint_name,
            tc.constraint_type,
            kcu.column_name
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
            AND tc.table_name = kcu.table_name
        WHERE tc.table_schema = :schema
        ORDER BY
            tc.table_name,
            tc.constraint_type,
            tc.constraint_name,
            kcu.ordinal_position;
    """

    return pd.read_sql(
        text(query),
        engine,
        params={"schema": SCHEMA},
    )


def get_columns(engine: Engine) -> pd.DataFrame:
    query = """
        SELECT
            table_schema,
            table_name,
            ordinal_position,
            column_name,
            data_type,
            udt_name,
            is_nullable,
            column_default,
            character_maximum_length,
            numeric_precision,
            numeric_scale
        FROM information_schema.columns
        WHERE table_schema = :schema
        ORDER BY table_name, ordinal_position;
    """

    return pd.read_sql(
        text(query),
        engine,
        params={"schema": SCHEMA},
    )


# ============================================================
# AUDITORIA POR TABELA
# ============================================================

def identify_market_table(
    table_name: str,
    columns: list[str],
) -> bool:
    table_words = set(
        re.split(r"[^a-z0-9]+", table_name.lower())
    )

    normalized_columns = {
        column.lower()
        for column in columns
    }

    has_market_name = bool(
        table_words.intersection(MARKET_TABLE_KEYWORDS)
    )

    has_ohlcv = {
        "open",
        "high",
        "low",
        "close",
    }.issubset(normalized_columns)

    has_symbol = any(
        candidate in normalized_columns
        for candidate in SYMBOL_COLUMN_CANDIDATES
    )

    has_time = any(
        candidate in normalized_columns
        for candidate in TIME_COLUMN_CANDIDATES
    )

    return has_market_name or has_ohlcv or (has_symbol and has_time)


def get_table_sample(
    engine: Engine,
    table_name: str,
    limit: int,
) -> pd.DataFrame:
    schema = safe_identifier(SCHEMA)
    table = safe_identifier(table_name)

    query = f"""
        SELECT *
        FROM "{schema}"."{table}"
        TABLESAMPLE SYSTEM (1)
        LIMIT :limit
    """

    try:
        dataframe = pd.read_sql(
            text(query),
            engine,
            params={"limit": limit},
        )

        # TABLESAMPLE pode retornar vazio em tabelas pequenas.
        if not dataframe.empty:
            return dataframe

    except SQLAlchemyError:
        pass

    fallback_query = f"""
        SELECT *
        FROM "{schema}"."{table}"
        LIMIT :limit
    """

    return pd.read_sql(
        text(fallback_query),
        engine,
        params={"limit": limit},
    )


def get_exact_row_count_for_small_table(
    engine: Engine,
    table_name: str,
    estimated_rows: int | None,
) -> int | None:
    """
    Executa COUNT(*) apenas em tabelas que parecem pequenas.
    """

    if estimated_rows is None:
        return None

    if estimated_rows > 500_000:
        return None

    schema = safe_identifier(SCHEMA)
    table = safe_identifier(table_name)

    query = f"""
        SELECT COUNT(*)
        FROM "{schema}"."{table}";
    """

    try:
        result = execute_scalar(engine, query)
        return int(result) if result is not None else None
    except SQLAlchemyError:
        return None


def analyze_temporal_range(
    engine: Engine,
    table_name: str,
    time_column: str,
) -> dict[str, Any]:
    schema = safe_identifier(SCHEMA)
    table = safe_identifier(table_name)
    column = safe_identifier(time_column)

    query = f"""
        SELECT
            MIN("{column}") AS minimum_value,
            MAX("{column}") AS maximum_value,
            COUNT("{column}") AS non_null_values,
            COUNT(*) - COUNT("{column}") AS null_values
        FROM "{schema}"."{table}";
    """

    try:
        dataframe = pd.read_sql(text(query), engine)

        if dataframe.empty:
            return {}

        return {
            key: serialize_value(value)
            for key, value in dataframe.iloc[0].to_dict().items()
        }

    except SQLAlchemyError as error:
        return {
            "error": str(error),
        }


def analyze_symbols(
    engine: Engine,
    table_name: str,
    symbol_column: str,
) -> dict[str, Any]:
    schema = safe_identifier(SCHEMA)
    table = safe_identifier(table_name)
    column = safe_identifier(symbol_column)

    distinct_query = f"""
        SELECT COUNT(DISTINCT "{column}")
        FROM "{schema}"."{table}";
    """

    top_query = f"""
        SELECT
            "{column}" AS symbol,
            COUNT(*) AS records
        FROM "{schema}"."{table}"
        WHERE "{column}" IS NOT NULL
        GROUP BY "{column}"
        ORDER BY records DESC
        LIMIT 30;
    """

    result: dict[str, Any] = {}

    try:
        distinct_count = execute_scalar(engine, distinct_query)
        result["distinct_symbols"] = (
            int(distinct_count)
            if distinct_count is not None
            else None
        )

        top_symbols = pd.read_sql(text(top_query), engine)
        result["top_symbols"] = top_symbols.to_dict(
            orient="records"
        )

    except SQLAlchemyError as error:
        result["error"] = str(error)

    return result

def count_distinct_values(series: pd.Series) -> int:
    """
    Conta valores distintos mesmo quando a coluna contém
    dicionários, listas ou outros objetos não hashable.
    """

    normalized_values = []

    for value in series.dropna():
        if isinstance(value, (dict, list, tuple, set)):
            try:
                normalized_values.append(
                    json.dumps(
                        value,
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    )
                )
            except (TypeError, ValueError):
                normalized_values.append(str(value))
        else:
            normalized_values.append(value)

    try:
        return len(set(normalized_values))
    except TypeError:
        return len(
            {
                json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                if isinstance(value, (dict, list, tuple, set))
                else str(value)
                for value in normalized_values
            }
        )

def analyze_sample(
    dataframe: pd.DataFrame,
) -> dict[str, Any]:
    if dataframe.empty:
        return {
            "sample_rows": 0,
            "sample_columns": 0,
            "columns": {},
        }

    column_report: dict[str, Any] = {}

    for column in dataframe.columns:
        series = dataframe[column]
        null_count = int(series.isna().sum())
        row_count = len(series)

        report: dict[str, Any] = {
            "dtype": str(series.dtype),
            "null_count": null_count,
            "null_percentage": round(
                (null_count / row_count) * 100,
                4,
            ),
            "distinct_in_sample": count_distinct_values(series),
        }

        non_null_series = series.dropna()

        if not non_null_series.empty:
            report["example_values"] = [
                serialize_value(value)
                for value in non_null_series.head(5).tolist()
            ]

        if pd.api.types.is_numeric_dtype(series):
            numeric_series = pd.to_numeric(
                series,
                errors="coerce",
            ).dropna()

            if not numeric_series.empty:
                report["numeric_statistics"] = {
                    "minimum": serialize_value(
                        numeric_series.min()
                    ),
                    "maximum": serialize_value(
                        numeric_series.max()
                    ),
                    "mean": serialize_value(
                        numeric_series.mean()
                    ),
                    "median": serialize_value(
                        numeric_series.median()
                    ),
                    "standard_deviation": serialize_value(
                        numeric_series.std()
                    ),
                }

        column_report[column] = report

    duplicate_rows = int(
        dataframe.duplicated(keep=False).sum()
    )

    return {
        "sample_rows": int(len(dataframe)),
        "sample_columns": int(len(dataframe.columns)),
        "duplicate_rows_in_sample": duplicate_rows,
        "duplicate_percentage_in_sample": round(
            (duplicate_rows / len(dataframe)) * 100,
            4,
        ),
        "memory_usage_bytes": int(
            dataframe.memory_usage(
                index=True,
                deep=True,
            ).sum()
        ),
        "columns": column_report,
    }


def check_ohlcv_quality(
    dataframe: pd.DataFrame,
) -> dict[str, Any]:
    normalized_columns = {
        column.lower(): column
        for column in dataframe.columns
    }

    required = ["open", "high", "low", "close"]

    if not all(
        column in normalized_columns
        for column in required
    ):
        return {
            "ohlcv_detected": False,
        }

    open_column = normalized_columns["open"]
    high_column = normalized_columns["high"]
    low_column = normalized_columns["low"]
    close_column = normalized_columns["close"]

    numeric = pd.DataFrame(
        {
            "open": pd.to_numeric(
                dataframe[open_column],
                errors="coerce",
            ),
            "high": pd.to_numeric(
                dataframe[high_column],
                errors="coerce",
            ),
            "low": pd.to_numeric(
                dataframe[low_column],
                errors="coerce",
            ),
            "close": pd.to_numeric(
                dataframe[close_column],
                errors="coerce",
            ),
        }
    )

    valid = numeric.dropna()

    if valid.empty:
        return {
            "ohlcv_detected": True,
            "valid_numeric_rows": 0,
        }

    invalid_high = (
        valid["high"]
        < valid[["open", "close", "low"]].max(axis=1)
    )

    invalid_low = (
        valid["low"]
        > valid[["open", "close", "high"]].min(axis=1)
    )

    non_positive_prices = (
        valid[["open", "high", "low", "close"]] <= 0
    ).any(axis=1)

    return {
        "ohlcv_detected": True,
        "valid_numeric_rows": int(len(valid)),
        "invalid_high_rows": int(invalid_high.sum()),
        "invalid_low_rows": int(invalid_low.sum()),
        "non_positive_price_rows": int(
            non_positive_prices.sum()
        ),
    }


def detect_duplicate_key_candidates(
    dataframe: pd.DataFrame,
    time_column: str | None,
    symbol_column: str | None,
) -> dict[str, Any]:
    candidates: list[str] = []

    if symbol_column:
        candidates.append(symbol_column)

    if time_column:
        candidates.append(time_column)

    normalized = {
        column.lower(): column
        for column in dataframe.columns
    }

    for candidate in [
        "interval",
        "timeframe",
        "exchange",
        "market_type",
    ]:
        if candidate in normalized:
            candidates.append(normalized[candidate])

    candidates = list(dict.fromkeys(candidates))

    if not candidates or dataframe.empty:
        return {
            "candidate_columns": candidates,
            "duplicates_in_sample": None,
        }

    available = dataframe[candidates].dropna(how="all")

    duplicate_count = int(
        available.duplicated(
            subset=candidates,
            keep=False,
        ).sum()
    )

    return {
        "candidate_columns": candidates,
        "duplicates_in_sample": duplicate_count,
        "duplicate_percentage_in_sample": round(
            (
                duplicate_count
                / max(len(available), 1)
            )
            * 100,
            4,
        ),
    }


def audit_table(
    engine: Engine,
    table_name: str,
    estimated_rows: int | None,
    table_columns: pd.DataFrame,
) -> dict[str, Any]:
    print(f"\nAuditando tabela: {table_name}")

    column_names = table_columns["column_name"].tolist()

    time_column = find_column(
        column_names,
        TIME_COLUMN_CANDIDATES,
    )

    symbol_column = find_column(
        column_names,
        SYMBOL_COLUMN_CANDIDATES,
    )

    market_table = identify_market_table(
        table_name,
        column_names,
    )

    sample = get_table_sample(
        engine,
        table_name,
        SAMPLE_SIZE,
    )

    report: dict[str, Any] = {
        "table_name": table_name,
        "estimated_rows": estimated_rows,
        "exact_rows_if_small": (
            get_exact_row_count_for_small_table(
                engine,
                table_name,
                estimated_rows,
            )
        ),
        "column_count": len(column_names),
        "column_names": column_names,
        "time_column_detected": time_column,
        "symbol_column_detected": symbol_column,
        "possible_market_table": market_table,
        "sample_analysis": analyze_sample(sample),
        "ohlcv_quality": check_ohlcv_quality(sample),
        "possible_duplicate_keys": (
            detect_duplicate_key_candidates(
                sample,
                time_column,
                symbol_column,
            )
        ),
    }

    if time_column:
        report["temporal_range"] = analyze_temporal_range(
            engine,
            table_name,
            time_column,
        )

    if symbol_column:
        report["symbol_analysis"] = analyze_symbols(
            engine,
            table_name,
            symbol_column,
        )

    if not sample.empty:
        sample_directory = OUTPUT_DIR / "amostras"
        sample_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        export_dataframe = sample.head(
            EXPORT_SAMPLE_SIZE
        )

        csv_path = (
            sample_directory
            / f"{table_name}_amostra.csv"
        )

        export_dataframe.to_csv(
            csv_path,
            index=False,
            encoding="utf-8-sig",
        )

        report["sample_file"] = str(csv_path)

    return report


# ============================================================
# RESUMO DE TRADING
# ============================================================

def build_trading_summary(
    table_reports: list[dict[str, Any]],
) -> dict[str, Any]:
    market_tables = [
        report
        for report in table_reports
        if report.get("possible_market_table")
    ]

    candidate_tables = []

    for report in market_tables:
        candidate_tables.append(
            {
                "table_name": report.get("table_name"),
                "estimated_rows": report.get(
                    "estimated_rows"
                ),
                "time_column": report.get(
                    "time_column_detected"
                ),
                "symbol_column": report.get(
                    "symbol_column_detected"
                ),
                "temporal_range": report.get(
                    "temporal_range"
                ),
                "symbol_analysis": report.get(
                    "symbol_analysis"
                ),
                "ohlcv_quality": report.get(
                    "ohlcv_quality"
                ),
            }
        )

    warnings: list[str] = []

    for report in market_tables:
        table_name = report.get("table_name")

        ohlcv = report.get("ohlcv_quality", {})

        if ohlcv.get("invalid_high_rows", 0) > 0:
            warnings.append(
                f"{table_name}: existem candles em que "
                f"high é menor que open, close ou low."
            )

        if ohlcv.get("invalid_low_rows", 0) > 0:
            warnings.append(
                f"{table_name}: existem candles em que "
                f"low é maior que open, close ou high."
            )

        if ohlcv.get("non_positive_price_rows", 0) > 0:
            warnings.append(
                f"{table_name}: existem preços iguais "
                f"ou menores que zero."
            )

        duplicate_data = report.get(
            "possible_duplicate_keys",
            {},
        )

        if (
            duplicate_data.get(
                "duplicates_in_sample",
                0,
            )
            or 0
        ) > 0:
            warnings.append(
                f"{table_name}: foram encontradas possíveis "
                f"duplicidades na chave "
                f"{duplicate_data.get('candidate_columns')}."
            )

        if not report.get("time_column_detected"):
            warnings.append(
                f"{table_name}: nenhuma coluna temporal "
                f"foi reconhecida automaticamente."
            )

        if not report.get("symbol_column_detected"):
            warnings.append(
                f"{table_name}: nenhuma coluna de ativo "
                f"foi reconhecida automaticamente."
            )

    return {
        "possible_market_tables_count": len(
            candidate_tables
        ),
        "possible_market_tables": candidate_tables,
        "warnings": warnings,
        "recommended_next_steps": [
            (
                "Selecionar a tabela principal de candles "
                "ou preços."
            ),
            (
                "Confirmar o intervalo de cada registro, "
                "por exemplo 1m, 5m ou 10m."
            ),
            (
                "Definir a chave única esperada, normalmente "
                "symbol + timestamp + timeframe + exchange."
            ),
            (
                "Verificar lacunas temporais e candles "
                "ausentes."
            ),
            (
                "Criar o primeiro dataset de treinamento "
                "sem modificar as tabelas de produção."
            ),
            (
                "Separar treino, validação e teste em "
                "ordem cronológica."
            ),
        ],
    }


# ============================================================
# EXECUÇÃO
# ============================================================

def main() -> int:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 70)
    print("AUDITORIA DO BANCO VINANCE")
    print("=" * 70)
    print(f"Schema: {SCHEMA}")
    print(f"Amostra por tabela: {SAMPLE_SIZE:,} linhas")
    print(f"Diretório de saída: {OUTPUT_DIR.resolve()}")

    try:
        engine = create_database_engine()

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        print("\nConexão com o PostgreSQL realizada.")

    except Exception as error:
        print(
            f"\nErro ao conectar ao banco:\n{error}",
            file=sys.stderr,
        )
        return 1

    try:
        database_information = get_database_information(
            engine
        )

        table_statistics = get_table_statistics(engine)
        columns = get_columns(engine)
        indexes = get_indexes(engine)
        constraints = get_constraints(engine)

        table_statistics.to_csv(
            OUTPUT_DIR / "01_tabelas_e_tamanhos.csv",
            index=False,
            encoding="utf-8-sig",
        )

        columns.to_csv(
            OUTPUT_DIR / "02_colunas.csv",
            index=False,
            encoding="utf-8-sig",
        )

        indexes.to_csv(
            OUTPUT_DIR / "03_indices.csv",
            index=False,
            encoding="utf-8-sig",
        )

        constraints.to_csv(
            OUTPUT_DIR / "04_restricoes.csv",
            index=False,
            encoding="utf-8-sig",
        )

        table_reports: list[dict[str, Any]] = []

        for _, table_row in table_statistics.iterrows():
            table_name = str(table_row["table_name"])

            if table_name in IGNORED_TABLES:
                print(
                    f"Ignorando tabela interna: {table_name}"
                )
                continue

            estimated_rows_raw = table_row.get(
                "estimated_rows"
            )

            estimated_rows = (
                int(estimated_rows_raw)
                if pd.notna(estimated_rows_raw)
                else None
            )

            table_columns = columns[
                columns["table_name"] == table_name
            ]

            try:
                report = audit_table(
                    engine=engine,
                    table_name=table_name,
                    estimated_rows=estimated_rows,
                    table_columns=table_columns,
                )

                table_reports.append(report)

            except Exception as error:
                print(
                    f"Erro ao auditar {table_name}: {error}",
                    file=sys.stderr,
                )

                table_reports.append(
                    {
                        "table_name": table_name,
                        "estimated_rows": estimated_rows,
                        "error": str(error),
                    }
                )

        trading_summary = build_trading_summary(
            table_reports
        )

        final_report = {
            "generated_at": datetime.now().isoformat(),
            "configuration": {
                "schema": SCHEMA,
                "sample_size": SAMPLE_SIZE,
                "export_sample_size": EXPORT_SAMPLE_SIZE,
                "output_directory": str(OUTPUT_DIR),
            },
            "database": database_information,
            "totals": {
                "tables_found": int(
                    len(table_statistics)
                ),
                "tables_audited": len(table_reports),
                "estimated_total_rows": int(
                    table_statistics[
                        "estimated_rows"
                    ].fillna(0).sum()
                ),
                "total_size_bytes": int(
                    table_statistics[
                        "total_size_bytes"
                    ].fillna(0).sum()
                ),
            },
            "trading_summary": trading_summary,
            "tables": table_reports,
        }

        with open(
            OUTPUT_DIR / "05_relatorio_completo.json",
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                final_report,
                file,
                ensure_ascii=False,
                indent=2,
                default=serialize_value,
            )

        market_table_dataframe = pd.DataFrame(
            trading_summary[
                "possible_market_tables"
            ]
        )

        if not market_table_dataframe.empty:
            market_table_dataframe.to_csv(
                OUTPUT_DIR
                / "06_tabelas_candidatas_trading.csv",
                index=False,
                encoding="utf-8-sig",
            )

        print("\n" + "=" * 70)
        print("AUDITORIA CONCLUÍDA")
        print("=" * 70)
        print(
            f"Tabelas encontradas: "
            f"{len(table_statistics)}"
        )
        print(
            f"Tabelas auditadas: "
            f"{len(table_reports)}"
        )
        print(
            f"Registros estimados: "
            f"{final_report['totals']['estimated_total_rows']:,}"
        )
        print(
            f"Tabelas candidatas para trading: "
            f"{trading_summary['possible_market_tables_count']}"
        )
        print(
            f"Alertas encontrados: "
            f"{len(trading_summary['warnings'])}"
        )
        print(
            f"\nArquivos gerados em:\n"
            f"{OUTPUT_DIR.resolve()}"
        )

        if trading_summary["warnings"]:
            print("\nPrincipais alertas:")

            for warning in trading_summary["warnings"][:20]:
                print(f"- {warning}")

        return 0

    except Exception as error:
        print(
            f"\nFalha durante a auditoria:\n{error}",
            file=sys.stderr,
        )
        return 1

    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())