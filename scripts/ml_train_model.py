
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.ml_training_service import train_model


def main() -> None:
    parser = argparse.ArgumentParser(description="FinanceOS ML training")
    parser.add_argument("--dataset-id", type=int, required=True)
    parser.add_argument("--model-type", default="random_forest", choices=["random_forest", "gradient_boosting", "gb", "ensemble_basic", "xgboost", "lightgbm"])
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--split-mode", default="temporal", choices=["temporal", "random"])
    parser.add_argument("--scaler", default="standard", choices=["none", "standard", "minmax"])
    parser.add_argument("--feature-selection", default="none", choices=["none", "importance", "correlation"])
    parser.add_argument("--top-features", type=int, default=20)
    parser.add_argument("--correlation-threshold", type=float, default=0.95)
    args = parser.parse_args()

    result = train_model(
        dataset_id=args.dataset_id,
        model_type=args.model_type,
        test_size=args.test_size,
        random_state=args.random_state,
        split_mode=args.split_mode,
        scaler=args.scaler,
        feature_selection=args.feature_selection,
        top_features=args.top_features,
        correlation_threshold=args.correlation_threshold,
    )
    print(result)


if __name__ == "__main__":
    main()
