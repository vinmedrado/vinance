from __future__ import annotations

from pathlib import Path

from backend.app.intelligence.ml.evaluate import hit_rate_top_n, mae, regression_metrics, rmse, spearman_correlation


def test_regression_metrics_basic_values():
    y_true = [0.10, -0.05, 0.20]
    y_pred = [0.08, -0.02, 0.16]
    metrics = regression_metrics(y_true, y_pred, top_n=2)
    assert metrics["mae"] is not None
    assert metrics["rmse"] is not None
    assert metrics["spearman_correlation"] is not None
    assert metrics["hit_rate_top_n"] is not None


def test_metrics_empty_series_return_none():
    assert mae([], []) is None
    assert rmse([], []) is None
    assert spearman_correlation([], []) is None
    assert hit_rate_top_n([], []) is None


def test_dataset_documents_future_target_and_no_lookahead():
    content = Path("backend/app/intelligence/ml/dataset.py").read_text(encoding="utf-8")
    assert "feature.date + timedelta(days=horizon_days)" in content
    assert "target_return" in content
    assert "date >= min_date" in content


def test_inference_has_fallback_when_model_absent():
    content = Path("backend/app/intelligence/ml/inference.py").read_text(encoding="utf-8")
    assert "feature_heuristic_fallback" in content
    assert "Modelo ML baseline não encontrado" in content


def test_recommendations_keep_heuristic_fallback(monkeypatch):
    from backend.app.intelligence import service

    calls = []

    def fake_rank(asset_class, assets, *, limit):
        calls.append((asset_class, list(assets), limit))
        return [{"ticker": f"{asset_class}-fallback", "score": 50}]

    monkeypatch.setattr(service, "rank_assets", fake_rank)
    assets = {asset_class: [object()] for asset_class in service.ASSET_CLASSES}

    ranked = service.rank_assets_by_class(assets, limit=3)

    assert set(ranked) == set(service.ASSET_CLASSES)
    assert all(items[0]["score"] == 50 for items in ranked.values())
    assert len(calls) == len(service.ASSET_CLASSES)


def test_no_deep_learning_imports_in_ml_baseline():
    ml_dir = Path("backend/app/intelligence/ml")
    content = "\n".join(path.read_text(encoding="utf-8") for path in ml_dir.glob("*.py"))
    forbidden_imports = ["import tensorflow", "import keras", "import torch", "from tensorflow", "from keras", "from torch", "from prophet", "import prophet"]
    assert not any(token in content.lower() for token in forbidden_imports)
