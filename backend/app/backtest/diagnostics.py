from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[3]
LOG_DIR = ROOT / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / 'backtest.log'


def get_backtest_logger(name: str = 'financeos.backtest') -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(stream)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger


class BacktestDiagnostics:
    def __init__(self, enabled: bool = True, logger: Optional[logging.Logger] = None):
        self.enabled = enabled
        self.logger = logger or get_backtest_logger()
        self.events = []

    def log(self, level: str, message: str, **payload: Any) -> None:
        if not self.enabled:
            return
        event: Dict[str, Any] = {
            'timestamp': datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
            'level': level.upper(),
            'message': message,
            **payload,
        }
        self.events.append(event)
        suffix = ''
        if payload:
            try:
                suffix = ' | ' + json.dumps(payload, ensure_ascii=False, default=str)
            except Exception:
                suffix = f' | {payload}'
        getattr(self.logger, level.lower(), self.logger.info)(message + suffix)

    def info(self, message: str, **payload: Any) -> None:
        self.log('INFO', message, **payload)

    def warning(self, message: str, **payload: Any) -> None:
        self.log('WARNING', message, **payload)

    def error(self, message: str, **payload: Any) -> None:
        self.log('ERROR', message, **payload)
