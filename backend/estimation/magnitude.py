"""Magnitude from observed losses: shrunk log-mean, prior dispersion held.

The honest position on magnitude is that accounting data rarely contains it.
A ledger records what you paid a vendor, not what their late delivery cost you
in expedited freight, lost margin and overtime. So for most engines this returns
the prior untouched, and the interface says so rather than implying otherwise.

Where losses ARE observable (a churned customer's revenue is the clearest case)
the log-mean shrinks toward the prior on the same principle as frequency.

Dispersion is deliberately NOT estimated until there are enough observations to
do it sanely. Under-observed sigma is the fastest route to an understated tail,
and an understated tail is the exact failure this product exists to prevent.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Pseudo-observations carried by the prior on the log-mean.
DEFAULT_PRIOR_STRENGTH = 5

# Below this many observations the prior sigma is held. Estimating dispersion
# from a handful of points reliably understates it.
MIN_OBS_FOR_SIGMA = 15


@dataclass(frozen=True)
class MagnitudePosterior:
    mu: float                 # log-scale location
    sigma: float              # log-scale dispersion
    weight_on_data: float
    n_observations: int
    sigma_is_prior: bool

    @property
    def median(self) -> float:
        return math.exp(self.mu)


def estimate_magnitude(
    prior_mu: float,
    prior_sigma: float,
    observed_losses: list[float],
    k: int = DEFAULT_PRIOR_STRENGTH,
) -> MagnitudePosterior:
    """Shrink the observed log-mean toward the prior.

    With no observations this returns the prior exactly, matching the frequency
    estimator's contract.
    """
    losses = [float(x) for x in (observed_losses or []) if x and float(x) > 0]
    n = len(losses)
    if n == 0:
        return MagnitudePosterior(prior_mu, prior_sigma, 0.0, 0, True)

    w = n / (n + k)
    logs = [math.log(x) for x in losses]
    post_mu = w * (sum(logs) / n) + (1.0 - w) * prior_mu

    sigma, sigma_is_prior = prior_sigma, True
    if n >= MIN_OBS_FOR_SIGMA:
        mean_log = sum(logs) / n
        var = sum((x - mean_log) ** 2 for x in logs) / (n - 1)
        observed_sigma = math.sqrt(var)
        # Never let a thin sample shrink the tail: dispersion may widen on
        # evidence, but it does not narrow below what the pack published.
        if observed_sigma > prior_sigma:
            sigma, sigma_is_prior = observed_sigma, False

    return MagnitudePosterior(post_mu, sigma, w, n, sigma_is_prior)


def to_magnitude_pair(
    posterior: MagnitudePosterior,
    prior_pair: tuple[float, float],
) -> tuple[float, float]:
    """Back to the (mode, p90) dollars an engine consumes.

    The pack expresses magnitude as (mode, P90) and `engines.fair` solves the
    lognormal from it. Rather than re-deriving that solve here, the estimated
    log-mean is applied as a ratio against the prior's, which preserves the
    pack's authored shape and moves its location by exactly what was observed.
    With no observations the ratio is 1.0 and the pair is returned untouched.
    """
    if posterior.n_observations == 0:
        return prior_pair
    mode, p90 = prior_pair
    prior_median = math.sqrt(max(mode, 1e-9) * max(p90, 1e-9))
    ratio = posterior.median / prior_median if prior_median > 0 else 1.0
    # Bounded for the same reason every other derived response is bounded: a
    # handful of unusual losses must not move the number by an order of
    # magnitude.
    ratio = max(0.5, min(2.0, ratio))
    return (mode * ratio, p90 * ratio)
