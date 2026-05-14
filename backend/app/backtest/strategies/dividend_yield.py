from typing import List
from ._common import BaseSelectionStrategy, safe_float


class DividendYieldStrategy(BaseSelectionStrategy):
    name = 'dividend_yield'

    def select(self, as_of_date: str) -> List[str]:
        rows = self.repository.get_strategy_universe(as_of_date, self.asset_class, self.tickers)
        ranked = []
        for row in self._filter_rows(rows):
            metrics = row.get('metrics') or {}
            dy = safe_float(metrics.get('dividend_yield_12m'), None)
            if dy is None:
                dy = safe_float(row.get('score_dividendos'), None)
            if dy is None:
                continue
            liq = safe_float(row.get('score_liquidez'), safe_float(metrics.get('liquidez_score'), 0))
            ranked.append((dy, liq or 0, row['ticker']))
        ranked.sort(reverse=True)
        return [ticker for _, __, ticker in ranked[:self.top_n]]
