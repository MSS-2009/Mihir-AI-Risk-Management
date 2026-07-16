"""Shared numeric helpers for the model library.

`risk_summary` is the canonical downside block every loss-type model emits so
the composite correlation model can consume them uniformly:
    {"expected_loss": float, "p95_loss": float, "label": str}
Loss is always the adverse-direction annual dollar magnitude (>= 0).
"""
from __future__ import annotations

import numpy as np


def clamp01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def lin_distress(v: float, healthy: float, bad: float) -> float:
    """0 when v is at the 'healthy' reference, 1 at the 'bad' reference, linear
    and clamped in between. Direction is inferred from healthy vs bad."""
    if bad == healthy:
        return 0.0
    return clamp01((v - healthy) / (bad - healthy))


def beta_params(mean: float, strength: float) -> tuple[float, float]:
    """(alpha, beta) for a Beta with the given mean and concentration."""
    mean = min(0.999, max(0.001, mean))
    return mean * strength, (1.0 - mean) * strength


def pctile(a: np.ndarray, q: float) -> float:
    return round(float(np.percentile(a, q)), 2)


# Probability grid the composite uses to reconstruct each domain's empirical
# marginal. Includes the tail (0.99) so amplification at P95 is well-supported.
_Q_GRID = [0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]


def risk_summary(losses: np.ndarray, label: str) -> dict:
    """Canonical downside block from a loss sample array. No trimming, the tail
    is the product. Carries a quantile grid + zero-mass so the composite model
    can rebuild the empirical marginal exactly, without shipping the raw array.
    """
    return {
        "expected_loss": round(float(losses.mean()), 2),
        "p95_loss": pctile(losses, 95),
        "std": round(float(losses.std()), 2),
        "prob_zero_loss": round(float((losses <= 0).mean()), 4),
        "quantiles": {str(q): pctile(losses, q * 100) for q in _Q_GRID},
        "label": label,
    }
