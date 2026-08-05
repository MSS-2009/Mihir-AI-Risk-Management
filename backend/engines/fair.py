"""FAIR marginal primitives: PERT frequency, lognormal magnitude.

Every engine in Avenoir is this same marginal specification wearing a different
label. A domain's annual loss is

    annual_loss = frequency (events/yr)  x  magnitude ($/event)

with frequency drawn from a PERT distribution over (min, mode, max) and
magnitude from a lognormal calibrated to (mode, P90).

The two closed-form means are exact and carry no Monte Carlo noise, which makes
them the tightest available regression test on calibration. Compare them against
a simulation with a tolerance (0.5% at n=50,000), never with equality: the
closed form is noiseless but the simulation it is measured against is not.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

# PERT shape parameter. 4.0 is the standard choice and puts moderate weight on
# the mode relative to the bounds.
PERT_LAMBDA = 4.0

# z for the 90th percentile of a standard normal.
Z90 = 1.2816


def pert_params(lef_min: float, lef_mode: float, lef_max: float) -> tuple[float, float, float]:
    """(alpha, beta, span) of the underlying Beta for a PERT(min, mode, max)."""
    if not (lef_min <= lef_mode <= lef_max):
        raise ValueError(f"PERT requires min <= mode <= max, got ({lef_min}, {lef_mode}, {lef_max})")
    span = max(lef_max - lef_min, 1e-9)
    a = 1.0 + PERT_LAMBDA * (lef_mode - lef_min) / span
    b = 1.0 + PERT_LAMBDA * (lef_max - lef_mode) / span
    return a, b, span


def pert_samples(lef_min, lef_mode, lef_max, n_sims: int, rng: np.random.Generator) -> np.ndarray:
    """Draw n_sims event frequencies from PERT(min, mode, max)."""
    a, b, span = pert_params(lef_min, lef_mode, lef_max)
    return lef_min + rng.beta(a, b, n_sims) * span


def pert_mean(lef_min: float, lef_mode: float, lef_max: float) -> float:
    """Closed-form PERT mean: (min + 4*mode + max) / 6. No simulation."""
    return (lef_min + PERT_LAMBDA * lef_mode + lef_max) / (PERT_LAMBDA + 2.0)


def lognormal_from_range(mode: float, p90: float) -> tuple[float, float]:
    """Solve (mu, sigma) of a lognormal from its mode and 90th percentile.

    mode = exp(mu - sigma^2)  and  p90 = exp(mu + 1.2816*sigma)

    Substituting mu gives a single equation in sigma, solved numerically with
    Brent's method. There is no analytic shortcut that preserves the tail, and
    the tail is the part of this product that matters.
    """
    if mode <= 0:
        raise ValueError(f"magnitude mode must be positive, got {mode}")
    if p90 <= mode:
        raise ValueError(
            f"magnitude P90 ({p90:,.0f}) must exceed the mode ({mode:,.0f}); "
            "a lognormal is right-skewed so its P90 is always above its mode"
        )

    def f(s: float) -> float:
        mu = np.log(mode) + s * s
        return float(np.exp(mu + Z90 * s) - p90)

    # f is increasing in s; bracket generously. sigma=3 spans a ~377,000x ratio.
    sigma = brentq(f, 1e-6, 3.0, xtol=1e-12, rtol=1e-14)
    mu = float(np.log(mode) + sigma * sigma)
    return mu, float(sigma)


def lognormal_mean(mu: float, sigma: float) -> float:
    """Closed-form lognormal mean: exp(mu + sigma^2/2). No simulation."""
    return float(np.exp(mu + sigma * sigma / 2.0))


def lognormal_from_uniforms(mu: float, sigma: float, u: np.ndarray) -> np.ndarray:
    """Inverse-CDF transform: uniforms -> lognormal magnitudes.

    This is where copula dependence enters the model. The uniforms carry the
    joint structure; each marginal simply maps its own column.
    """
    u = np.clip(u, 1e-12, 1.0 - 1e-12)
    return np.exp(mu + sigma * norm.ppf(u))


@dataclass(frozen=True)
class Marginal:
    """One risk domain's calibrated loss distribution.

    Engines produce these. The composite consumes them jointly. An engine never
    runs its own Monte Carlo and gets glued to the others afterwards, because
    that would destroy the joint dependence the whole product is about.
    """

    key: str                       # engine id, e.g. "third_party_failure"
    label: str                     # industry-facing name, e.g. "Supplier failure"
    lef: tuple[float, float, float]        # (min, mode, max) events per year
    magnitude: tuple[float, float]         # (mode, P90) dollars per event
    mu: float = field(init=False)
    sigma: float = field(init=False)

    def __post_init__(self):
        mu, sigma = lognormal_from_range(*self.magnitude)
        object.__setattr__(self, "mu", mu)
        object.__setattr__(self, "sigma", sigma)

    @property
    def expected_frequency(self) -> float:
        return pert_mean(*self.lef)

    @property
    def expected_magnitude(self) -> float:
        return lognormal_mean(self.mu, self.sigma)

    @property
    def expected_annual_loss(self) -> float:
        """Closed form. Frequency and magnitude are independent within a domain,
        so E[F x M] = E[F] x E[M]."""
        return self.expected_frequency * self.expected_magnitude

    def scaled(self, factor: float) -> "Marginal":
        """Revenue-scaled copy. Magnitudes scale, frequencies stay flat."""
        return Marginal(
            key=self.key,
            label=self.label,
            lef=self.lef,
            magnitude=(self.magnitude[0] * factor, self.magnitude[1] * factor),
        )

    def public(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "lef_min": self.lef[0],
            "lef_mode": self.lef[1],
            "lef_max": self.lef[2],
            "magnitude_mode": self.magnitude[0],
            "magnitude_p90": self.magnitude[1],
            "mu": round(self.mu, 6),
            "sigma": round(self.sigma, 6),
            "expected_annual_loss": round(self.expected_annual_loss, 2),
        }


def closed_form_expected_loss(marginals: list[Marginal]) -> float:
    """Portfolio expected annual loss, exactly, with no simulation.

    Expectation is linear, so correlation does not move this number at all.
    That is not a bug to hide, it is the honest headline: dependence changes the
    tail, never the average.
    """
    return float(sum(m.expected_annual_loss for m in marginals))


def frequency_draws(
    marginals: list[Marginal], n_sims: int, seed: int
) -> np.ndarray:
    """(n_sims, d) frequency draws, one column per domain.

    Held constant across correlated and independent runs, and across every
    robustness perturbation, so those comparisons isolate dependence.
    """
    rng = np.random.default_rng(seed)
    return np.column_stack([pert_samples(*m.lef, n_sims, rng) for m in marginals])


def portfolio_losses(
    marginals: list[Marginal], freqs: np.ndarray, uniforms: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Annual loss per scenario.

    Returns (total (n_sims,), per_domain (n_sims, d)). No outlier trimming: in
    risk the tail is the product.
    """
    cols = [
        freqs[:, i] * lognormal_from_uniforms(m.mu, m.sigma, uniforms[:, i])
        for i, m in enumerate(marginals)
    ]
    per_domain = np.column_stack(cols)
    return per_domain.sum(axis=1), per_domain
