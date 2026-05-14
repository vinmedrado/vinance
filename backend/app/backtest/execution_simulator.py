from typing import Optional, Tuple

class ExecutionSimulator:
    def __init__(self, repository):
        self.repository = repository

    def next_close(self, ticker: str, signal_date: str) -> Optional[Tuple[str, float]]:
        row = self.repository.get_next_close(ticker, signal_date)
        if not row:
            return None
        return str(row['date'])[:10], float(row['close'])
