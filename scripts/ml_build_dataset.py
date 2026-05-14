
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.ml_dataset_service import build_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="FinanceOS ML dataset builder")
    parser.add_argument("--asset-class", default="all")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--target", default="future_return_positive", choices=["future_return_positive", "future_return_regression", "future_return_class"])
    parser.add_argument("--horizon-days", type=int, default=21)
    parser.add_argument("--min-quality-score", type=float, default=45)
    parser.add_argument("--min-history-days", type=int, default=180)
    args = parser.parse_args()

    result = build_dataset(
        asset_class=args.asset_class,
        start_date=args.start_date,
        end_date=args.end_date,
        target=args.target,
        horizon_days=args.horizon_days,
        min_quality_score=args.min_quality_score,
        min_history_days=args.min_history_days,
    )
    print(result)


if __name__ == "__main__":
    main()
