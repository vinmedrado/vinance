from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = {
    "exchange", "symbol", "interval", "open_time", "open", "high", "low", "close", "volume"
}


def validate_candles(frame: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        return [f"Colunas ausentes: {sorted(missing)}"]
    if frame.empty:
        return ["Nenhum candle recebido."]
    if frame["open_time"].isna().any():
        errors.append("Existem timestamps nulos.")
    if frame.duplicated(["exchange", "symbol", "interval", "open_time"]).any():
        errors.append("Existem candles duplicados pela chave natural.")
    numeric = frame[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any():
        errors.append("Existem preços não numéricos.")
    if (numeric <= 0).any().any():
        errors.append("Existem preços menores ou iguais a zero.")
    if (numeric["high"] < numeric[["open", "close", "low"]].max(axis=1)).any():
        errors.append("Existem máximas inconsistentes.")
    if (numeric["low"] > numeric[["open", "close", "high"]].min(axis=1)).any():
        errors.append("Existem mínimas inconsistentes.")
    return errors
