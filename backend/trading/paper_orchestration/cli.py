from __future__ import annotations

import argparse
import json
import sys

from backend.trading.config import get_settings
from backend.trading.storage.database import create_sync_engine

from .service import ManualPaperOrchestrator


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Explicit, unscheduled Trading V2 Paper orchestration"
    )
    parser.add_argument("command", choices=("status", "run-once"))
    args = parser.parse_args()
    engine = None
    try:
        engine = create_sync_engine(get_settings().database_url)
        orchestrator = ManualPaperOrchestrator(engine)
        result = orchestrator.status() if args.command == "status" else orchestrator.run_once()
    except Exception:
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "error_code": "TRADING_ORCHESTRATION_UNAVAILABLE",
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    finally:
        if engine is not None:
            engine.dispose()
    print(json.dumps(result, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
