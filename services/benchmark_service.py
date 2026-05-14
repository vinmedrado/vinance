from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd

CDI_ANNUAL_RATE = 0.11  # simplificação inicial determinística: 11% a.a.
IBOV_SYMBOL = "^BVSP"


def _to_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value)[:10])
    except Exception:
        return None


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def calculate_alpha(strategy_return: Any, benchmark_return: Any) -> float:
    """Alpha simples: retorno da estratégia menos retorno do benchmark."""
    return _num(strategy_return) - _num(benchmark_return)


def calculate_benchmark_return(df: pd.DataFrame) -> Dict[str, float]:
    """Calcula retorno total/anualizado a partir de uma série com coluna close/Close."""
    if df is None or df.empty:
        return {"return": 0.0, "annual_return": 0.0}

    close_col = "close" if "close" in df.columns else "Close" if "Close" in df.columns else None
    if not close_col:
        return {"return": 0.0, "annual_return": 0.0}

    series = pd.to_numeric(df[close_col], errors="coerce").dropna()
    if len(series) < 2:
        return {"return": 0.0, "annual_return": 0.0}

    total_return = float(series.iloc[-1] / series.iloc[0] - 1.0)
    try:
        if isinstance(df.index, pd.DatetimeIndex) and len(df.index) >= 2:
            days = max(1, int((df.index[-1] - df.index[0]).days))
        else:
            days = max(1, len(series))
        annual_return = float((1.0 + total_return) ** (365.0 / days) - 1.0)
    except Exception:
        annual_return = total_return
    return {"return": total_return, "annual_return": annual_return}


def _cdi_return(start_date: Any, end_date: Any, annual_rate: float = CDI_ANNUAL_RATE) -> Dict[str, float]:
    start = _to_datetime(start_date)
    end = _to_datetime(end_date)
    if not start or not end or end <= start:
        return {"cdi_return": 0.0, "cdi_annual_return": annual_rate}
    days = max(1, (end - start).days)
    total = float((1.0 + annual_rate) ** (days / 365.0) - 1.0)
    return {"cdi_return": total, "cdi_annual_return": annual_rate}


def _ibov_from_yfinance(start_date: Any, end_date: Any) -> Dict[str, float]:
    try:
        import yfinance as yf  # type: ignore

        start = str(start_date)[:10]
        end = str(end_date)[:10]
        df = yf.download(IBOV_SYMBOL, start=start, end=end, progress=False, auto_adjust=False)
        if df is None or df.empty:
            return {"ibov_return": 0.0, "ibov_annual_return": 0.0}
        calc = calculate_benchmark_return(df)
        return {"ibov_return": calc["return"], "ibov_annual_return": calc["annual_return"]}
    except Exception:
        return {"ibov_return": 0.0, "ibov_annual_return": 0.0}


def get_benchmark_data(start_date: Any, end_date: Any) -> Dict[str, float]:
    """Retorna benchmark IBOV + CDI sem alterar banco.

    IBOV usa yfinance quando disponível; CDI usa aproximação determinística anual.
    Em caso de falha, retorna zeros para manter a UI resiliente.
    """
    ibov = _ibov_from_yfinance(start_date, end_date)
    cdi = _cdi_return(start_date, end_date)
    return {**ibov, **cdi}
