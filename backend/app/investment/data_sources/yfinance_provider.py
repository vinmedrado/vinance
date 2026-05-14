from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass
class MarketSeries:
    symbol: str
    prices: list[dict[str, Any]]
    dividends: list[dict[str, Any]]
    metadata: dict[str, Any]
    warnings: list[str]


class YFinanceProvider:
    """Provider de mercado via yfinance.

    Não gera dados fictícios. Se yfinance não estiver instalado ou a API não retornar dados,
    devolve listas vazias com aviso explícito para o usuário/sistema.
    """

    source = "yfinance"

    def fetch_history(self, symbol: str, start: date | None = None, end: date | None = None) -> MarketSeries:
        warnings: list[str] = []
        try:
            import yfinance as yf  # type: ignore
        except Exception:
            return MarketSeries(symbol=symbol, prices=[], dividends=[], metadata={}, warnings=["Biblioteca yfinance não instalada. Adicione yfinance ao ambiente para sincronizar preços reais."])

        ticker = yf.Ticker(symbol)
        try:
            hist = ticker.history(start=start.isoformat() if start else None, end=end.isoformat() if end else None, auto_adjust=False)
        except Exception as exc:
            return MarketSeries(symbol=symbol, prices=[], dividends=[], metadata={}, warnings=[f"Falha ao consultar yfinance: {exc}"])

        prices: list[dict[str, Any]] = []
        dividends: list[dict[str, Any]] = []
        if hist is None or hist.empty:
            warnings.append("yfinance não retornou histórico para o ticker informado.")
        else:
            for idx, row in hist.iterrows():
                dt = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else datetime.fromisoformat(str(idx))
                close = row.get("Close")
                volume = row.get("Volume")
                prices.append({"date": dt, "close": float(close) if close == close else None, "volume": float(volume) if volume == volume else None, "raw": {k: None if v != v else float(v) for k, v in row.to_dict().items() if isinstance(v, (int, float))}})
                div = row.get("Dividends", 0) or 0
                if div > 0:
                    dividends.append({"date": dt, "amount": float(div), "raw": {"dividend": float(div)}})
        info: dict[str, Any] = {}
        try:
            raw_info = ticker.info or {}
            info = {k: raw_info.get(k) for k in ("shortName", "longName", "currency", "country", "quoteType", "sector") if raw_info.get(k) is not None}
        except Exception as exc:
            warnings.append(f"Metadados indisponíveis no yfinance: {exc}")
        return MarketSeries(symbol=symbol, prices=prices, dividends=dividends, metadata=info, warnings=warnings)
