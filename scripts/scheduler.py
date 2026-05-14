
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("financeos.scheduler")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(LOG_DIR / "data_layer.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler())

JOBS = [
    [sys.executable, "scripts/run_data_layer_incremental.py"],
    [sys.executable, "scripts/run_analysis_engine.py", "--limit", "500"],
]

def run_job(cmd: list[str]) -> bool:
    label = " ".join(cmd)
    logger.info("job_start %s", label)
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=60 * 60)
        if proc.stdout:
            logger.info("job_stdout %s", proc.stdout[-4000:])
        if proc.stderr:
            logger.warning("job_stderr %s", proc.stderr[-4000:])
        if proc.returncode != 0:
            logger.error("job_failed %s returncode=%s", label, proc.returncode)
            return False
        logger.info("job_success %s", label)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception("job_exception %s error=%s", label, exc)
        return False

def run_cycle() -> None:
    logger.info("scheduler_cycle_start %s", datetime.now().isoformat(timespec="seconds"))
    for cmd in JOBS:
        run_job(cmd)
    logger.info("scheduler_cycle_end")

def main() -> int:
    parser = argparse.ArgumentParser(description="FinanceOS scheduler simples para operação contínua")
    parser.add_argument("--once", action="store_true", help="Executa um ciclo e encerra")
    parser.add_argument("--interval-hours", type=float, default=24.0, help="Intervalo entre ciclos")
    args = parser.parse_args()
    if args.once:
        run_cycle()
        return 0
    sleep_seconds = max(60, int(args.interval_hours * 3600))
    logger.info("scheduler_started interval_seconds=%s", sleep_seconds)
    while True:
        run_cycle()
        time.sleep(sleep_seconds)

if __name__ == "__main__":
    raise SystemExit(main())
