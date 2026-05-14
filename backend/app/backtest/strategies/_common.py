import json
from typing import Any, Dict, Iterable, List, Optional, Sequence


ASSET_CLASSES = {'all', 'equity', 'fii', 'etf', 'bdr', 'crypto', 'index', 'currency', 'commodity'}


def normalize_tickers(tickers: Optional[Sequence[str]]) -> Optional[List[str]]:
    if not tickers:
        return None
    values = [str(t).strip().upper() for t in tickers if str(t).strip()]
    return values or None


def parse_metrics_json(value: Any) -> Dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == '':
            return default
        return float(value)
    except Exception:
        return default


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


class BaseSelectionStrategy:
    name = 'base'

    def __init__(
        self,
        repository,
        asset_class: str = 'all',
        top_n: int = 10,
        min_score: Optional[float] = None,
        tickers: Optional[Sequence[str]] = None,
        min_liquidity_score: Optional[float] = None,
        **params: Any,
    ):
        asset_class = str(asset_class or 'all').strip().lower()
        if asset_class not in ASSET_CLASSES:
            raise ValueError(f'asset_class inválido: {asset_class}')
        self.repository = repository
        self.asset_class = asset_class
        self.top_n = max(1, int(top_n or 10))
        self.min_score = min_score
        self.tickers = normalize_tickers(tickers)
        self.min_liquidity_score = min_liquidity_score
        self.params = params
        self.mode = str(params.get('mode', 'no_lookahead')).strip().lower()
        self.last_diagnostics: Dict[str, Any] = {}

    def select(self, as_of_date: str) -> List[str]:
        raise NotImplementedError

    def _filter_rows(self, rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in rows:
            ticker = str(row.get('ticker') or '').upper().strip()
            if not ticker:
                continue
            if self.tickers and ticker not in self.tickers:
                continue

            row_class = str(row.get('asset_class') or '').strip().lower()
            if self.asset_class != 'all' and row_class and row_class != self.asset_class:
                continue

            if self.min_score is not None and safe_float(row.get('score_total'), -1) < float(self.min_score):
                continue

            metrics = parse_metrics_json(row.get('metrics') or row.get('metrics_json'))
            row['metrics'] = metrics

            if self.min_liquidity_score is not None:
                liq = safe_float(row.get('score_liquidez'), None)
                if liq is None:
                    liq = safe_float(metrics.get('liquidez_score'), None)
                if liq is None or liq < float(self.min_liquidity_score):
                    continue
            out.append(row)
        return out
