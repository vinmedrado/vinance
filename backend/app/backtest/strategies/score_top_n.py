from typing import List
from ._common import BaseSelectionStrategy


class ScoreTopNStrategy(BaseSelectionStrategy):
    name = 'score_top_n'

    def select(self, as_of_date: str) -> List[str]:
        rows, diagnostics = self.repository.select_score_top_n(
            as_of_date=as_of_date,
            asset_class=self.asset_class,
            top_n=self.top_n,
            min_score=self.min_score,
            tickers=self.tickers,
            mode=getattr(self, 'mode', self.params.get('mode', 'no_lookahead')),
        )
        self.last_diagnostics = diagnostics
        return [str(row['ticker']).upper() for row in rows if row.get('ticker')]
