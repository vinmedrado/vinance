from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("financeos")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def log_event(event: str, **payload: Any) -> None:
    logger.info(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "event": event, **payload}, ensure_ascii=False, default=str))
