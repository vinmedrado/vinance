
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.final_ranking_service import get_ranked_assets_by_market, VALID_MARKETS


def main() -> int:
    tenant_id = None
    ok = True
    for market in VALID_MARKETS:
        rows = get_ranked_assets_by_market(market, limit=10, tenant_id=tenant_id)
        print(f"{market}: {len(rows)} ativos")
        if rows:
            scores = [r["score_final"] for r in rows]
            ordered = scores == sorted(scores, reverse=True)
            print(f"  líder: {rows[0]['ticker']} score={rows[0]['score_final']} classificação={rows[0]['classification']}")
            print(f"  ordenado: {ordered}")
            ok = ok and ordered
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
