from __future__ import annotations

import numpy as np


def binary_auroc(labels: np.ndarray, scores: np.ndarray) -> float:
    y = np.asarray(labels, dtype=np.int64)
    s = np.asarray(scores, dtype=np.float64)
    if y.shape != s.shape or set(np.unique(y).tolist()) != {0, 1}:
        raise ValueError("AUROC requires aligned labels containing both classes")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(s.size, dtype=np.float64)
    ranks[order] = np.arange(1, s.size + 1, dtype=np.float64)
    for value in np.unique(s):
        tied = np.flatnonzero(s == value)
        ranks[tied] = np.mean(ranks[tied])
    positive = y == 1
    n_positive = int(np.sum(positive))
    n_negative = int(np.sum(~positive))
    return float((np.sum(ranks[positive]) - n_positive * (n_positive + 1) / 2) / (n_positive * n_negative))


def binary_nll(labels: np.ndarray, probabilities: np.ndarray) -> float:
    y = np.asarray(labels, dtype=np.float64)
    p = np.clip(np.asarray(probabilities, dtype=np.float64), 1e-8, 1.0 - 1e-8)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def brier_score(labels: np.ndarray, probabilities: np.ndarray) -> float:
    return float(np.mean((np.asarray(probabilities, dtype=np.float64) - np.asarray(labels, dtype=np.float64)) ** 2))


def expected_calibration_error(
    labels: np.ndarray, probabilities: np.ndarray, bins: int = 10
) -> float:
    y = np.asarray(labels, dtype=np.float64)
    p = np.asarray(probabilities, dtype=np.float64)
    edges = np.linspace(0.0, 1.0, int(bins) + 1)
    total = y.size
    value = 0.0
    for index in range(int(bins)):
        mask = (p >= edges[index]) & (p < edges[index + 1] if index + 1 < bins else p <= 1.0)
        if np.any(mask):
            value += float(np.sum(mask) / total) * abs(float(np.mean(p[mask]) - np.mean(y[mask])))
    return value


def risk_coverage(errors: np.ndarray, risk_scores: np.ndarray) -> dict:
    error = np.asarray(errors, dtype=np.float64)
    risk = np.asarray(risk_scores, dtype=np.float64)
    if error.shape != risk.shape or error.ndim != 1 or error.size < 2:
        raise ValueError("risk-coverage requires aligned one-dimensional arrays")
    order = np.argsort(risk)
    sorted_error = error[order]
    coverages = np.arange(1, error.size + 1, dtype=np.float64) / error.size
    selective_risk = np.cumsum(sorted_error) / np.arange(1, error.size + 1)
    aurc = float(np.trapz(selective_risk, coverages))
    retained = {}
    for coverage in (0.9, 0.75, 0.5):
        count = max(1, int(np.floor(coverage * error.size)))
        values = sorted_error[:count]
        retained[str(coverage)] = {
            "median_error": float(np.median(values)),
            "p90_error": float(np.percentile(values, 90)),
        }
    return {"aurc": aurc, "retained": retained}


def spearman_correlation(first: np.ndarray, second: np.ndarray) -> float:
    x = _average_ranks(np.asarray(first, dtype=np.float64))
    y = _average_ranks(np.asarray(second, dtype=np.float64))
    if x.size < 2 or np.std(x) <= 0 or np.std(y) <= 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def _average_ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(values.size, dtype=np.float64)
    ranks[order] = np.arange(values.size, dtype=np.float64)
    for value in np.unique(values):
        mask = values == value
        ranks[mask] = np.mean(ranks[mask])
    return ranks
