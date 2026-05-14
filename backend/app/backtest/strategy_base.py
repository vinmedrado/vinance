from abc import ABC, abstractmethod
from typing import List

class StrategyBase(ABC):
    name = 'base'

    @abstractmethod
    def select(self, as_of_date: str) -> List[str]:
        raise NotImplementedError
