from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd


class MarketDataProvider(ABC):
    @abstractmethod
    def fetch_candles(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        raise NotImplementedError
