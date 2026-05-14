from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_step(name: str, cmd: list[str]) -> int:
    print(f"\n[pipeline] >>> {name}")
    print("[pipeline]", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode != 0:
        print(f"[pipeline][WARNING] etapa '{name}' terminou com código {proc.returncode}; seguindo com próximas etapas.")
    else:
        print(f"[pipeline] etapa '{name}' OK")
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline controlado do catálogo: validação cacheada + qualidade + sync assets.")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--asset-class", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-age-days", type=int, default=7)
    args = parser.parse_args()

    common = []
    if args.limit:
        common += ["--limit", str(args.limit)]
    if args.asset_class:
        common += ["--asset-class", args.asset_class]

    validate_cmd = [PYTHON, "scripts/validate_asset_catalog.py", *common, "--status", "all", "--max-age-days", str(args.max_age_days)]
    if args.force:
        validate_cmd.append("--force")

    quality_cmd = [PYTHON, "scripts/update_asset_quality_scores.py", *common]
    sync_cmd = [PYTHON, "scripts/sync_assets_from_catalog.py", *common]

    codes = []
    codes.append(run_step("validar catálogo", validate_cmd))
    codes.append(run_step("atualizar quality scores", quality_cmd))
    codes.append(run_step("sincronizar assets ativos", sync_cmd))

    print("\n[pipeline] resumo final")
    print(f"- limit: {args.limit}")
    print(f"- asset_class: {args.asset_class or 'all'}")
    print(f"- force: {args.force}")
    print(f"- max_age_days: {args.max_age_days}")
    print(f"- etapas_com_warning: {sum(1 for c in codes if c != 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
