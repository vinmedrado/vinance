from __future__ import annotations

from sqlalchemy.engine import Engine

from .config import DEFAULT_CONFIG, MLEngineConfig
from .dataset import DatasetRepository


class MLEngineRepository:
    def __init__(self, engine: Engine, config: MLEngineConfig = DEFAULT_CONFIG) -> None:
        self.engine = engine
        self.config = config
        self.datasets = DatasetRepository(engine, config=config)

    def load_dataset(self, *, symbol: str, interval: str, target_name: str, limit: int | None = None):
        return self.datasets.load_dataset(symbol=symbol, interval=interval, target_name=target_name, limit=limit)
