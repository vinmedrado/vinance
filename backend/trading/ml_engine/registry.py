from __future__ import annotations

from collections.abc import Callable

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from .config import DEFAULT_CONFIG, MLEngineConfig


ModelFactory = Callable[[], object]


class LabelEncodedClassifier:
    def __init__(self, estimator) -> None:
        self.estimator = estimator
        self.classes_: np.ndarray | None = None

    def fit(self, x_data, y_data):
        self.classes_ = np.array(sorted(np.unique(y_data)))
        encoded = np.searchsorted(self.classes_, np.asarray(y_data))
        self.estimator.fit(x_data, encoded)
        return self

    def predict(self, x_data):
        encoded = self.estimator.predict(x_data).astype(int)
        return self.classes_[encoded]

    def predict_proba(self, x_data):
        return self.estimator.predict_proba(x_data)


def model_registry(config: MLEngineConfig = DEFAULT_CONFIG) -> dict[str, ModelFactory]:
    registry: dict[str, ModelFactory] = {
        "logistic_regression": lambda: LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=config.random_state,
        ),
        "random_forest": lambda: RandomForestClassifier(
            n_estimators=120,
            max_depth=8,
            min_samples_leaf=5,
            class_weight="balanced_subsample",
            random_state=config.random_state,
            n_jobs=-1,
        ),
        "extra_trees": lambda: ExtraTreesClassifier(
            n_estimators=120,
            max_depth=8,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=config.random_state,
            n_jobs=-1,
        ),
        "hist_gradient_boosting": lambda: HistGradientBoostingClassifier(
            max_iter=120,
            learning_rate=0.05,
            max_leaf_nodes=31,
            random_state=config.random_state,
        ),
    }

    try:
        from xgboost import XGBClassifier

        registry["xgboost"] = lambda: LabelEncodedClassifier(
            XGBClassifier(
                n_estimators=120,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.9,
                objective="multi:softprob",
                eval_metric="mlogloss",
                random_state=config.random_state,
                n_jobs=1,
            )
        )
    except Exception:
        pass

    return registry
