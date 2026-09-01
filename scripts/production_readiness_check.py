
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.production_health_service import run_full_healthcheck


def main() -> int:
    result = run_full_healthcheck()
    status = result.get("status", "fail")

    print(f"STATUS: {status.upper()}")
    for check in result.get("checks", []):
        print(f"- {check['name']}: {check['status'].upper()} — {check['message']}")

    print("\nAções recomendadas:")
    for check in result.get("checks", []):
        if check["status"] == "fail":
            print(f"FAIL: corrigir {check['name']} — {check['message']}")
        elif check["status"] == "warn":
            print(f"WARN: revisar {check['name']} — {check['message']}")

    if status == "pass":
        return 0
    if status == "warn":
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
