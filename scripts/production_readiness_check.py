
from __future__ import annotations

from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.production_health_service import run_full_healthcheck


def check_sqlite_usage() -> list[str]:
    hits = []
    forbidden_terms = ["sqlite3", "financas.db", "data/financas.db", "sqlite+aiosqlite"]
    allowed = {
        "scripts/migrate_sqlite_to_postgres.py",
        "scripts/production_readiness_check.py",
    }
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = Path(dirpath) / filename
            rel = str(path.relative_to(ROOT))
            if rel in allowed:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            if any(term in content for term in forbidden_terms):
                hits.append(rel)
    return hits


def main() -> int:
    sqlite_hits = check_sqlite_usage()
    result = run_full_healthcheck()
    status = result.get("status", "fail")

    if sqlite_hits:
        status = "fail"

    print(f"STATUS: {status.upper()}")
    for check in result.get("checks", []):
        print(f"- {check['name']}: {check['status'].upper()} — {check['message']}")

    if sqlite_hits:
        print("\nFAIL: SQLite residual detectado:")
        for hit in sqlite_hits:
            print(f"- {hit}")

    print("\nAções recomendadas:")
    if sqlite_hits:
        print("FAIL: remover referências SQLite listadas acima.")
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
