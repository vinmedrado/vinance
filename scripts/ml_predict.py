
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.ml_prediction_service import predict


def main() -> None:
    parser = argparse.ArgumentParser(description="FinanceOS ML prediction")
    parser.add_argument("--model-id", type=int, required=True)
    parser.add_argument("--asset-class", default="all")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--min-quality-score", type=float, default=45)
    parser.add_argument("--min-history-days", type=int, default=180)
    args = parser.parse_args()

    result = predict(
        model_id=args.model_id,
        asset_class=args.asset_class,
        limit=args.limit,
        min_quality_score=args.min_quality_score,
        min_history_days=args.min_history_days,
    )
    print(result)


if __name__ == "__main__":
    main()
