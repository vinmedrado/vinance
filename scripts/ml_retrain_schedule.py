
from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.ml_model_registry import get_best_model
from services.ml_training_service import train_model

def main():
    model = get_best_model()
    if not model:
        print({"status": "no_model"})
        return
    # Placeholder seguro: retreina dataset do melhor modelo.
    result = train_model(dataset_id=int(model["dataset_id"]), model_type="random_forest", split_mode="temporal")
    print(result)

if __name__ == "__main__":
    main()
