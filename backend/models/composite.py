"""Composite cross-domain risk correlation, the differentiator.

Standalone risk models treat each domain independently. Reality doesn't: a
country shock strains a concentrated supplier, whose distress compresses margin,
which raises delivery and price exposure. Risks correlate, so the real tail is
worse than the sum of the parts.

Method (deterministic, numpy-only, no scipy):
  1. Rebuild each domain's empirical loss marginal from the quantile grid +
     zero-mass its model reported (no lognormal fitting, so genuinely fat tails
     survive; no raw arrays shipped).
  2. Draw correlated standard normals via the Cholesky factor of a documented,
     editable correlation matrix. An *empirical Gaussian copula* maps each
     domain's normal draw to its marginal by rank, exact marginals, target
     rank-correlation, and no normal-CDF/erf needed.
  3. Aggregate per scenario. Compare the correlated aggregate tail against the
     independent aggregate ("risks apart") to size the compounding, and rank the
     domain pairs that drive it.

The headline: "your risks are X% worse together than apart, driven by A <-> B."
"""
from __future__ import annotations

import numpy as np

from .registry import ModelSpec, register

# Default pairwise correlations, first-order economic linkages for an
# industrial-equipment distributor. Editable in the UI; documented here and on
# the methodology page. Unlisted pairs default to MILD_DEFAULT (risks tend to
# co-move mildly under stress). Keys use registry model keys.
DEFAULT_CORRELATIONS: dict[tuple[str, str], float] = {
    ("country", "supplier_concentration"): 0.50,
    ("country", "delivery"): 0.45,
    ("country", "supplier_health"): 0.35,
    ("country", "price"): 0.30,
    ("supplier_concentration", "delivery"): 0.40,
    ("supplier_concentration", "supplier_health"): 0.40,
    ("supplier_health", "price"): 0.30,
    ("delivery", "price"): 0.30,
    ("market", "price"): 0.35,
    ("market", "country"): 0.30,
    ("cyber", "supplier_health"): 0.10,
}
MILD_DEFAULT = 0.15
CYBER_DEFAULT = 0.10  # cyber is largely idiosyncratic

_Q_GRID = [0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]


def _pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def default_rho(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if a == "cyber" or b == "cyber":
        base = CYBER_DEFAULT
    else:
        base = MILD_DEFAULT
    return DEFAULT_CORRELATIONS.get(_pair(a, b), base)


def build_correlation_matrix(keys: list[str], overrides: dict | None = None) -> np.ndarray:
    """Symmetric correlation matrix from defaults + user overrides.
    `overrides` maps "a|b" -> rho."""
    overrides = overrides or {}
    n = len(keys)
    R = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = keys[i], keys[j]
            key = f"{_pair(a, b)[0]}|{_pair(a, b)[1]}"
            rho = float(overrides.get(key, default_rho(a, b)))
            rho = max(-0.99, min(0.99, rho))
            R[i, j] = R[j, i] = rho
    return R


def nearest_psd(R: np.ndarray) -> tuple[np.ndarray, bool]:
    """Project to the nearest positive-semi-definite correlation matrix by
    clipping negative eigenvalues and renormalising the diagonal to 1. Returns
    (matrix, adjusted?)."""
    R = (R + R.T) / 2
    w, V = np.linalg.eigh(R)
    if (w >= 1e-10).all():
        return R, False
    w_clipped = np.clip(w, 1e-8, None)
    B = (V * w_clipped) @ V.T
    d = np.sqrt(np.clip(np.diag(B), 1e-12, None))
    C = B / np.outer(d, d)
    np.fill_diagonal(C, 1.0)
    return C, True


def _marginal_from_summary(rs: dict, n: int) -> np.ndarray:
    """Sorted (ascending) length-n sample of a domain's loss marginal, rebuilt
    from its reported quantile grid and zero-mass."""
    q = rs.get("quantiles", {})
    probs = [0.0] + _Q_GRID + [1.0]
    vals = [0.0]
    for g in _Q_GRID:
        vals.append(float(q.get(str(g), rs.get("expected_loss", 0.0))))
    # Enforce monotonicity, then a small tail extrapolation beyond p99.
    for i in range(1, len(vals)):
        vals[i] = max(vals[i], vals[i - 1])
    tail = vals[-1] + (vals[-1] - vals[-2])  # linear step past p99
    vals.append(max(tail, vals[-1]))
    u = (np.arange(n) + 0.5) / n
    return np.interp(u, probs, vals)


def composite_risk_correlation(
    domain_summaries: dict,
    correlation_overrides: dict | None = None,
    n_sims: int = 20000,
    seed: int = 42,
):
    """Correlated aggregate of per-domain loss distributions via an empirical
    Gaussian copula. See module docstring for the method.

    `domain_summaries`: {model_key: risk_summary dict}. Needs >= 2 domains.
    """
    keys = list(domain_summaries.keys())
    d = len(keys)
    if d < 2:
        return {"model": "composite_risk_correlation", "insufficient_domains": True}

    rng = np.random.default_rng(seed)

    # Sorted marginals (ascending) per domain.
    margins = np.stack([_marginal_from_summary(domain_summaries[k], n_sims) for k in keys])

    R = build_correlation_matrix(keys, correlation_overrides)
    R_psd, adjusted = nearest_psd(R)
    L = np.linalg.cholesky(R_psd)

    def aggregate(corr_matrix_factor):
        """Rank-map correlated normals onto each sorted marginal."""
        if corr_matrix_factor is None:
            Z = rng.standard_normal((n_sims, d))
        else:
            Z = rng.standard_normal((n_sims, d)) @ corr_matrix_factor.T
        cols = np.empty((n_sims, d))
        for i in range(d):
            ranks = np.argsort(np.argsort(Z[:, i]))
            cols[:, i] = margins[i][ranks]
        return cols

    corr_cols = aggregate(L)
    indep_cols = aggregate(None)
    agg_corr = corr_cols.sum(axis=1)
    agg_indep = indep_cols.sum(axis=1)

    expected_total = float(sum(domain_summaries[k]["expected_loss"] for k in keys))
    naive_sum_p95 = float(sum(domain_summaries[k]["p95_loss"] for k in keys))
    indep_p95 = float(np.percentile(agg_indep, 95))
    corr_p95 = float(np.percentile(agg_corr, 95))
    amplification = (corr_p95 - indep_p95) / indep_p95 if indep_p95 > 0 else 0.0

    # Pair contribution to the *compounding* is the covariance term
    # rho_ij * std_i * std_j, but only positive correlation compounds, and a
    # near-zero correlation on a huge-variance domain is size, not coupling. So
    # attribution weights by the correlation itself; the headline driver must
    # clear a meaningful-coupling threshold.
    stds = np.array([float(domain_summaries[k].get("std", corr_cols[:, i].std()))
                     for i, k in enumerate(keys)])
    labels = {k: domain_summaries[k].get("label", k) for k in keys}
    pairs = []
    for i in range(d):
        for j in range(i + 1, d):
            rho = float(R_psd[i, j])
            contrib = float(max(rho, 0.0) * stds[i] * stds[j])
            pairs.append({
                "a": keys[i], "b": keys[j],
                "a_label": labels[keys[i]], "b_label": labels[keys[j]],
                "rho": round(rho, 3),
                "contribution": round(contrib, 2),
            })
    pairs.sort(key=lambda p: p["contribution"], reverse=True)
    total_contrib = sum(p["contribution"] for p in pairs) or 1.0
    for p in pairs:
        p["share"] = round(p["contribution"] / total_contrib, 3)

    # Headline driver: the biggest contributor among genuinely-coupled pairs.
    MEANINGFUL_RHO = 0.25
    coupled = [p for p in pairs if p["rho"] >= MEANINGFUL_RHO]
    top = coupled[0] if coupled else (pairs[0] if pairs else None)
    return {
        "model": "composite_risk_correlation",
        "domains": keys,
        "expected_total_loss": round(expected_total, 2),
        "independent_p95": round(indep_p95, 2),
        "correlated_p95": round(corr_p95, 2),
        "naive_sum_p95": round(naive_sum_p95, 2),
        "amplification_pct": round(amplification, 4),
        "correlated_p99": round(float(np.percentile(agg_corr, 99)), 2),
        "headline": (
            f"Your risks are {amplification * 100:.0f}% worse together than apart"
            + (f", driven mainly by {top['a_label']} ↔ {top['b_label']} coupling."
               if top else ".")
        ),
        "top_pairs": pairs[:5],
        "correlation_matrix": {
            "keys": keys,
            "labels": [labels[k] for k in keys],
            "matrix": [[round(float(R_psd[i, j]), 3) for j in range(d)] for i in range(d)],
            "psd_adjusted": adjusted,
        },
        "assumptions": {
            "method": "empirical Gaussian copula over per-domain loss marginals",
            "n_sims": n_sims,
            "psd_adjusted": adjusted,
        },
    }


register(
    ModelSpec(
        key="composite",
        name="Composite risk correlation",
        version="1.0.0",
        domain="Cross-domain",
        method=(
            "Empirical Gaussian copula: rebuilds each domain's loss marginal from "
            "its simulated quantiles, draws correlated scenarios via the Cholesky "
            "factor of a documented correlation matrix (PSD-projected), and "
            "compares the correlated aggregate tail against the independent one to "
            "size the compounding and rank the pairs that drive it."
        ),
        fn=composite_risk_correlation,
        params=[],
        outputs=[
            {"key": "amplification_pct", "label": "Worse together than apart", "type": "percent"},
            {"key": "correlated_p95", "label": "Composite tail (P95)", "type": "currency"},
            {"key": "independent_p95", "label": "If risks were independent (P95)", "type": "currency"},
            {"key": "expected_total_loss", "label": "Expected total loss", "type": "currency"},
        ],
        runnable=False,
    )
)
