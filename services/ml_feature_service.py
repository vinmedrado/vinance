
from __future__ import annotations

from typing import Any
from db import pg_compat as dbcompat
import pandas as pd
import numpy as np

from services.ml_common import (
    bootstrap_ml_tables, connect, table_exists, table_columns, first_existing
)


PRICE_TABLE_CANDIDATES = ["asset_prices", "prices", "historical_prices"]
ASSET_TABLE_CANDIDATES = ["assets", "asset_catalog"]


def _find_price_table(conn: dbcompat.Connection) -> str | None:
    for t in PRICE_TABLE_CANDIDATES:
        if table_exists(conn, t):
            return t
    return None


def _find_asset_table(conn: dbcompat.Connection) -> str | None:
    for t in ASSET_TABLE_CANDIDATES:
        if table_exists(conn, t):
            return t
    return None


def load_price_data(conn: dbcompat.Connection, asset_class: str = "all", start_date: str | None = None, end_date: str | None = None) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    table = _find_price_table(conn)
    if not table:
        return pd.DataFrame(), ["Nenhuma tabela de preços encontrada."]

    cols = table_columns(conn, table)
    ticker_col = first_existing(cols, ["ticker", "symbol", "asset_symbol"])
    asset_id_col = first_existing(cols, ["asset_id", "id_asset"])
    date_col = first_existing(cols, ["date", "price_date", "datetime", "created_at"])
    close_col = first_existing(cols, ["close", "adjusted_close", "adj_close", "price", "close_price"])
    volume_col = first_existing(cols, ["volume", "volume_traded", "avg_volume"])

    if not date_col or not close_col:
        return pd.DataFrame(), [f"Tabela {table} sem colunas mínimas de data/preço."]

    select_cols = [c for c in [ticker_col, asset_id_col, date_col, close_col, volume_col] if c]
    sql = f"SELECT {', '.join(select_cols)} FROM {table} WHERE {close_col} IS NOT NULL"
    params: list[Any] = []
    if start_date:
        sql += f" AND {date_col} >= ?"
        params.append(start_date)
    if end_date:
        sql += f" AND {date_col} <= ?"
        params.append(end_date)

    df = pd.read_sql_query(sql, conn, params=params)
    if df.empty:
        return df, ["Sem dados de preço para os filtros informados."]

    rename = {date_col: "date", close_col: "close"}
    if ticker_col:
        rename[ticker_col] = "ticker"
    if asset_id_col:
        rename[asset_id_col] = "asset_id"
    if volume_col:
        rename[volume_col] = "volume"
    df = df.rename(columns=rename)

    if "ticker" not in df.columns:
        if "asset_id" in df.columns:
            df["ticker"] = df["asset_id"].astype(str)
            warnings.append("Ticker não encontrado; usando asset_id como ticker.")
        else:
            df["ticker"] = "UNKNOWN"
            warnings.append("Ticker/asset_id não encontrados; usando UNKNOWN.")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    else:
        df["volume"] = np.nan

    df = df.dropna(subset=["date", "close"]).sort_values(["ticker", "date"])
    return df, warnings


def load_catalog_features(conn: dbcompat.Connection) -> pd.DataFrame:
    table = _find_asset_table(conn)
    if not table:
        return pd.DataFrame(columns=["ticker", "asset_class", "data_quality_score", "reliability_status"])

    cols = table_columns(conn, table)
    ticker_col = first_existing(cols, ["ticker", "symbol", "asset_symbol", "code"])
    class_col = first_existing(cols, ["asset_class", "class", "type"])
    quality_col = first_existing(cols, ["data_quality_score", "quality_score", "score_quality", "quality"])
    reliability_col = first_existing(cols, ["reliability_status", "status", "validation_status"])

    if not ticker_col:
        return pd.DataFrame(columns=["ticker", "asset_class", "data_quality_score", "reliability_status"])

    select_cols = [ticker_col]
    for c in [class_col, quality_col, reliability_col]:
        if c and c not in select_cols:
            select_cols.append(c)
    df = pd.read_sql_query(f"SELECT {', '.join(select_cols)} FROM {table}", conn)
    rename = {ticker_col: "ticker"}
    if class_col:
        rename[class_col] = "asset_class"
    if quality_col:
        rename[quality_col] = "data_quality_score"
    if reliability_col:
        rename[reliability_col] = "reliability_status"
    df = df.rename(columns=rename)

    if "asset_class" not in df.columns:
        df["asset_class"] = "unknown"
    if "data_quality_score" not in df.columns:
        df["data_quality_score"] = 0
    if "reliability_status" not in df.columns:
        df["reliability_status"] = "unknown"

    df["data_quality_score"] = pd.to_numeric(df["data_quality_score"], errors="coerce").fillna(0)
    return df.drop_duplicates(subset=["ticker"])


def build_features(asset_class: str = "all", start_date: str | None = None, end_date: str | None = None) -> tuple[pd.DataFrame, list[str]]:
    with connect() as conn:
        bootstrap_ml_tables(conn)
        prices, warnings = load_price_data(conn, asset_class, start_date, end_date)
        catalog = load_catalog_features(conn)

    if prices.empty:
        return pd.DataFrame(), warnings

    frames = []
    for ticker, g in prices.groupby("ticker", dropna=False):
        g = g.sort_values("date").copy()
        g["return_5d"] = g["close"].pct_change(5)
        g["return_21d"] = g["close"].pct_change(21)
        g["return_63d"] = g["close"].pct_change(63)
        daily_ret = g["close"].pct_change()
        g["volatility_21d"] = daily_ret.rolling(21).std()
        g["volatility_63d"] = daily_ret.rolling(63).std()
        roll_max = g["close"].rolling(63, min_periods=1).max()
        g["drawdown_63d"] = (g["close"] / roll_max) - 1
        mm50 = g["close"].rolling(50).mean()
        mm200 = g["close"].rolling(200).mean()
        g["distance_mm50"] = (g["close"] / mm50) - 1
        g["distance_mm200"] = (g["close"] / mm200) - 1
        g["trend_strength"] = g["return_21d"].fillna(0) - g["volatility_21d"].fillna(0)
        g["avg_volume_21d"] = g["volume"].rolling(21).mean()
        g["avg_volume_63d"] = g["volume"].rolling(63).mean()
        frames.append(g)

    df = pd.concat(frames, ignore_index=True)
    if not catalog.empty:
        df = df.merge(catalog, on="ticker", how="left")
    else:
        df["asset_class"] = "unknown"
        df["data_quality_score"] = 0
        df["reliability_status"] = "unknown"

    if asset_class and asset_class != "all" and "asset_class" in df.columns:
        filtered = df[df["asset_class"].astype(str).str.lower() == asset_class.lower()]
        if not filtered.empty:
            df = filtered
        else:
            warnings.append(f"Filtro asset_class={asset_class} não encontrou catálogo correspondente; mantendo preços disponíveis.")

    feature_cols = [
        "return_5d", "return_21d", "return_63d",
        "volatility_21d", "volatility_63d", "drawdown_63d",
        "distance_mm50", "distance_mm200", "trend_strength",
        "avg_volume_21d", "avg_volume_63d", "data_quality_score",
    ]
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["reliability_status"] = df.get("reliability_status", "unknown").fillna("unknown").astype(str)
    df["asset_class"] = df.get("asset_class", "unknown").fillna("unknown").astype(str)
    return df, warnings


def latest_feature_frame(asset_class: str = "all", limit: int | None = None) -> tuple[pd.DataFrame, list[str]]:
    df, warnings = build_features(asset_class=asset_class)
    if df.empty:
        return df, warnings
    latest = df.sort_values("date").groupby("ticker", as_index=False).tail(1)
    latest = latest.sort_values("date", ascending=False)
    if limit:
        latest = latest.head(int(limit))
    return latest.reset_index(drop=True), warnings
