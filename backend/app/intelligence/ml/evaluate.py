from __future__ import annotations

import math
from statistics import mean
from typing import Iterable, Sequence


def _clean_pairs(y_true: Sequence[float], y_pred: Sequence[float]) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for actual, pred in zip(y_true, y_pred, strict=False):
        if actual is None or pred is None:
            continue
        if math.isfinite(float(actual)) and math.isfinite(float(pred)):
            pairs.append((float(actual), float(pred)))
    return pairs


def mae(y_true: Sequence[float], y_pred: Sequence[float]) -> float | None:
    pairs = _clean_pairs(y_true, y_pred)
    if not pairs:
        return None
    return mean(abs(actual - pred) for actual, pred in pairs)


def rmse(y_true: Sequence[float], y_pred: Sequence[float]) -> float | None:
    pairs = _clean_pairs(y_true, y_pred)
    if not pairs:
        return None
    return math.sqrt(mean((actual - pred) ** 2 for actual, pred in pairs))


def _ranks(values: Iterable[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(indexed)
    index = 0
    while index < len(indexed):
        end = index
        while end + 1 < len(indexed) and indexed[end + 1][1] == indexed[index][1]:
            end += 1
        avg_rank = (index + end + 2) / 2.0
        for pos in range(index, end + 1):
            ranks[indexed[pos][0]] = avg_rank
        index = end + 1
    return ranks


def spearman_correlation(y_true: Sequence[float], y_pred: Sequence[float]) -> float | None:
    pairs = _clean_pairs(y_true, y_pred)
    if len(pairs) < 3:
        return None
    true_ranks = _ranks([pair[0] for pair in pairs])
    pred_ranks = _ranks([pair[1] for pair in pairs])
    mean_true = mean(true_ranks)
    mean_pred = mean(pred_ranks)
    numerator = sum((a - mean_true) * (b - mean_pred) for a, b in zip(true_ranks, pred_ranks, strict=True))
    denom_true = math.sqrt(sum((a - mean_true) ** 2 for a in true_ranks))
    denom_pred = math.sqrt(sum((b - mean_pred) ** 2 for b in pred_ranks))
    if denom_true == 0 or denom_pred == 0:
        return None
    return numerator / (denom_true * denom_pred)


def hit_rate_top_n(y_true: Sequence[float], y_pred: Sequence[float], *, top_n: int = 5) -> float | None:
    pairs = _clean_pairs(y_true, y_pred)
    if not pairs:
        return None
    clean_top_n = max(1, min(top_n, len(pairs)))
    predicted_top = sorted(range(len(pairs)), key=lambda idx: pairs[idx][1], reverse=True)[:clean_top_n]
    hits = sum(1 for idx in predicted_top if pairs[idx][0] > 0)
    return hits / clean_top_n


def regression_metrics(y_true: Sequence[float], y_pred: Sequence[float], *, top_n: int = 5) -> dict[str, float | None]:
    return {
        "mae": mae(y_true, y_pred),
        "rmse": rmse(y_true, y_pred),
        "spearman_correlation": spearman_correlation(y_true, y_pred),
        "hit_rate_top_n": hit_rate_top_n(y_true, y_pred, top_n=top_n),
    }
