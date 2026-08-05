"""Second-order uncertainty: how much the answer depends on the correlation
matrix nobody actually knows.

Every vendor in this category runs Monte Carlo; the sampler is commodity. The
binding constraint is that the correlation matrix is expert judgment with no loss
data behind it. Competitors hand-wave it and then report a confident P99 as
though the matrix were known. This module measures that instead:

  robustness_band       the envelope of the answer across a neighbourhood of
                        plausible dependence structures
  dependence_fragility  which single pair the answer is most sensitive to, so
                        the customer knows exactly where refining an estimate
                        buys the most and what they can safely ignore

THE FIXED-DRAWS RULE
--------------------
Both sweeps reuse ONE `CopulaDraws` object and ONE frequency-draw array, varying
only the correlation matrix. This is a correctness requirement, not a speed
optimization. At eps=0.05 the true band spread is around 3.8% while P99 sampling
noise at 20k sims is around 2.4%: re-randomising per draw would report mostly
noise, and the number would be meaningless.

We claim robustness, never accuracy. Accuracy needs validation against realized
losses over years and is unfalsifiable today. Robustness is provable now because
it is a visible computation.
"""
from __future__ import annotations

import numpy as np

from .constants import DEFAULT_SEED, N_SIMS_SWEEP
from .copula import draw_copula_inputs, perturbed_matrix
from .fair import Marginal, frequency_draws
from .composite import run_portfolio

# "How confident are you in these relationships?"
EPS_LEVELS = {"conservative": 0.05, "moderate": 0.10, "uncertain": 0.20}
DEFAULT_EPS = 0.10
DEFAULT_DRAWS = 60
FRAGILITY_DELTA = 0.25


def _fixed_inputs(marginals: list[Marginal], n_sims: int, seed: int):
    """The shared draws. Everything downstream varies only the matrix."""
    return (
        draw_copula_inputs(len(marginals), n_sims, seed),
        frequency_draws(marginals, n_sims, seed + 1),
    )


def robustness_band(
    marginals: list[Marginal],
    base_corr: np.ndarray,
    eps: float = DEFAULT_EPS,
    n_draws: int = DEFAULT_DRAWS,
    n_sims: int = N_SIMS_SWEEP,
    seed: int = DEFAULT_SEED,
) -> dict:
    """Envelope of portfolio P95/P99 over a neighbourhood of dependence structures."""
    draws, freqs = _fixed_inputs(marginals, n_sims, seed)
    rng = np.random.default_rng(seed)

    point = run_portfolio(marginals, base_corr, draws, freqs)
    p95_point, p99_point = point.pct(95), point.pct(99)

    p95s, p99s = [], []
    for _ in range(n_draws):
        m = perturbed_matrix(base_corr, eps, rng)
        r = run_portfolio(marginals, m, draws, freqs)   # SAME draws, SAME freqs
        p95s.append(r.pct(95))
        p99s.append(r.pct(99))
    p95s, p99s = np.array(p95s), np.array(p99s)

    lo99, hi99 = float(p99s.min()), float(p99s.max())
    return {
        "eps": eps,
        "n_draws": n_draws,
        "n_sims": n_sims,
        "p99_point": round(p99_point, 2),
        "p99_low": round(lo99, 2),
        "p99_high": round(hi99, 2),
        "p99_spread_pct": round((hi99 - lo99) / p99_point, 4) if p99_point else 0.0,
        "worst_case_vs_point": round(hi99 / p99_point - 1, 4) if p99_point else 0.0,
        "p95_point": round(p95_point, 2),
        "p95_low": round(float(p95s.min()), 2),
        "p95_high": round(float(p95s.max()), 2),
        "method": (
            "Correlation matrix perturbed by symmetric noise (sd=eps), projected to "
            "the nearest positive-definite correlation matrix. Monte Carlo draws held "
            "fixed across all perturbations so the spread measures dependence "
            "misspecification rather than sampling noise."
        ),
    }


def dependence_fragility(
    marginals: list[Marginal],
    base_corr: np.ndarray,
    delta: float = FRAGILITY_DELTA,
    n_sims: int = N_SIMS_SWEEP,
    seed: int = DEFAULT_SEED,
    top_n: int | None = None,
) -> list[dict]:
    """Rank domain pairs by how much the answer swings when their correlation moves.

    The top entry is the highest-value sentence this product produces: it tells
    the customer which single relationship to refine, and by implication which
    ones they can leave alone.
    """
    from .copula import nearest_pd

    draws, freqs = _fixed_inputs(marginals, n_sims, seed)
    d = base_corr.shape[0]
    out = []
    for i in range(d):
        for j in range(i + 1, d):
            hi = base_corr.copy()
            hi[i, j] = hi[j, i] = min(base_corr[i, j] + delta, 0.95)
            lo = base_corr.copy()
            lo[i, j] = lo[j, i] = max(base_corr[i, j] - delta, -0.95)
            p_hi = run_portfolio(marginals, nearest_pd(hi), draws, freqs).pct(99)
            p_lo = run_portfolio(marginals, nearest_pd(lo), draws, freqs).pct(99)
            out.append(
                {
                    "pair": [marginals[i].key, marginals[j].key],
                    "labels": [marginals[i].label, marginals[j].label],
                    "rho": round(float(base_corr[i, j]), 3),
                    "is_default": bool(abs(base_corr[i, j] - 0.20) < 1e-9),
                    "p99_swing": round(abs(p_hi - p_lo), 2),
                }
            )
    out.sort(key=lambda r: -r["p99_swing"])
    return out[:top_n] if top_n else out


def robustness_assessment(
    marginals: list[Marginal],
    base_corr: np.ndarray,
    eps: float = DEFAULT_EPS,
    n_sims: int = N_SIMS_SWEEP,
    seed: int = DEFAULT_SEED,
) -> dict:
    """Both sweeps, plus the plain-language read of the band."""
    band = robustness_band(marginals, base_corr, eps=eps, n_sims=n_sims, seed=seed)
    fragility = dependence_fragility(marginals, base_corr, n_sims=n_sims, seed=seed)
    return {
        "robustness": band,
        "dependence_fragility": fragility,
        "eps_levels": EPS_LEVELS,
        "reading": _read_band(band, fragility),
    }


def _read_band(band: dict, fragility: list[dict]) -> str:
    """One honest sentence about what the band means. A tight band is a
    reassuring finding and worth saying out loud, since no competitor measures
    it at all."""
    spread = band["p99_spread_pct"]
    if spread < 0.05:
        verdict = "Your answer is highly robust to how these relationships are set"
    elif spread < 0.12:
        verdict = "Your answer is reasonably robust to how these relationships are set"
    else:
        verdict = "Your answer is sensitive to how these relationships are set"
    if not fragility:
        return f"{verdict}."
    top = fragility[0]
    tail = (
        " That pair is currently at the default estimate, so refining it would tighten "
        "your range more than any other input."
        if top["is_default"]
        else " Refining that pair would tighten your range more than any other input."
    )
    return (
        f"{verdict}: the P99 moves {spread:.1%} across plausible dependence structures. "
        f"It depends most on the relationship between {top['labels'][0].lower()} and "
        f"{top['labels'][1].lower()}.{tail}"
    )
