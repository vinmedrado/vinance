
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")

def configure_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    targets = {
        "financeos.api": "api.log",
        "financeos.data_layer": "data_layer.log",
        "financeos.analysis": "analysis.log",
        "financeos.backtest": "backtest.log",
    }
    for logger_name, filename in targets.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        logger.propagate = True
        if not any(isinstance(h, RotatingFileHandler) and getattr(h, 'baseFilename', '').endswith(filename) for h in logger.handlers):
            handler = RotatingFileHandler(LOG_DIR / filename, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
            handler.setFormatter(formatter)
            logger.addHandler(handler)

    root_logger = logging.getLogger()
    if not root_logger.handlers:
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        root_logger.addHandler(stream)
    root_logger.setLevel(logging.INFO)
