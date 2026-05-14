from typing import List, Optional, Sequence
from .strategy_base import StrategyBase

class StrategyScoreTopN(StrategyBase):
    name = 'score_top_n'

    def __init__(self, repository, top_n: int = 10, asset_class: str = 'all', min_score: Optional[float] = None, tickers: Optional[Sequence[str]] = None, mode: str = 'no_lookahead'):
        self.repository = repository
        self.top_n = int(top_n)
        self.asset_class = asset_class
        self.min_score = min_score
        self.tickers = tickers
        self.mode = mode
        self.last_diagnostics = {}

    def select(self, as_of_date: str) -> List[str]:
        rows, diagnostics = self.repository.select_score_top_n(
            as_of_date=as_of_date,
            asset_class=self.asset_class,
            top_n=self.top_n,
            min_score=self.min_score,
            tickers=self.tickers,
            mode=self.mode,
        )
        self.last_diagnostics = diagnostics
        return [str(row['ticker']).upper() for row in rows if row.get('ticker')]
