from typing import List
from ._common import BaseSelectionStrategy, safe_float


class LowVolatilityStrategy(BaseSelectionStrategy):
    name = 'low_volatility'

    def select(self, as_of_date: str) -> List[str]:
        min_return = self.params.get('min_return_90d')
        rows = self.repository.get_strategy_universe(as_of_date, self.asset_class, self.tickers)
        ranked = []
        for row in self._filter_rows(rows):
            metrics = row.get('metrics') or {}
            vol = safe_float(metrics.get('volatilidade_90d'), None)
            if vol is None:
                continue
            if min_return is not None and safe_float(metrics.get('retorno_90d'), -999) < float(min_return):
                continue
            ranked.append((vol, row['ticker']))
        ranked.sort(key=lambda x: x[0])
        return [ticker for _, ticker in ranked[:self.top_n]]
