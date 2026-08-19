"""The sweep that caught the bias, kept so it cannot come back.

Moved into backend/tests/ when B2 lands; here it is the evidence for the plan.
"""
import numpy as np

TRUE_MEAN, SHAPE = 1.10, 2.50
PRIOR_MEAN, PRIOR_STRENGTH = 0.458, 3.0


def pooled(n, years, rng):
    rates = rng.gamma(SHAPE, TRUE_MEAN / SHAPE, n)
    events = rng.poisson(rates * years)
    posterior = (PRIOR_MEAN * PRIOR_STRENGTH + events) / (PRIOR_STRENGTH + years)
    return posterior.mean(), events.sum() / (n * years)


def test_raw_statistics_recover_the_population_rate():
    rng = np.random.default_rng(20260819)
    for n, y in [(8, 1.0), (8, 3.0), (60, 3.0), (200, 3.0), (1000, 5.0)]:
        raw = np.mean([pooled(n, y, rng)[1] for _ in range(2000)])
        assert abs(raw / TRUE_MEAN - 1) < 0.02, (n, y, raw)


def test_pooling_posterior_means_stays_biased_at_every_size():
    """The property that makes this bias and not noise: more peers do not help."""
    rng = np.random.default_rng(20260819)
    errors = []
    for n in (8, 60, 200, 1000):
        pm = np.mean([pooled(n, 3.0, rng)[0] for _ in range(2000)])
        errors.append(pm / TRUE_MEAN - 1)
    assert all(e < -0.20 for e in errors), errors
    assert abs(errors[0] - errors[-1]) < 0.10, "bias must not wash out with N"
