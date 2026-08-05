"""CP1: FAIR marginal and copula primitives.

The headline test compares the closed-form expected loss against a simulation.
That comparison must carry a tolerance: the closed form is exact, but the
simulation it is measured against is not. Asserting equality would fail on
correct code and send you hunting a bug that does not exist.
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engines.constants import (  # noqa: E402
    CLOSED_FORM_TOL_10K,
    CLOSED_FORM_TOL_50K,
    DEFAULT_SEED,
    N_SIMS,
)
from engines.copula import (  # noqa: E402
    BASELINE_CORRELATION,
    build_matrix,
    draw_copula_inputs,
    ensure_pd,
    independent_uniforms,
    is_pd,
    nearest_pd,
    perturbed_matrix,
    require_pd,
    uniforms_for,
)
from engines.fair import (  # noqa: E402
    Marginal,
    closed_form_expected_loss,
    frequency_draws,
    lognormal_from_range,
    lognormal_mean,
    pert_mean,
    pert_samples,
    portfolio_losses,
)

# The industrial-distribution domain set, used as the standing fixture.
FIXTURE = [
    Marginal("input_cost_shock", "Tariff shock", (0.30, 0.80, 1.50), (450_000, 1_400_000)),
    Marginal("third_party_failure", "Vendor failure", (0.15, 0.40, 1.00), (250_000, 900_000)),
    Marginal("schedule_disruption", "Logistics delay", (0.40, 1.00, 2.20), (150_000, 700_000)),
    Marginal("inventory_stockout", "Stockout", (0.30, 0.70, 1.60), (200_000, 800_000)),
    Marginal("site_disruption", "Warehouse outage", (0.08, 0.20, 0.50), (400_000, 1_800_000)),
    Marginal("cyber_loss", "Cyber incident", (0.05, 0.15, 0.45), (180_000, 1_100_000)),
]
KEYS = [m.key for m in FIXTURE]
PAIRS = {
    ("third_party_failure", "schedule_disruption"): 0.65,
    ("schedule_disruption", "inventory_stockout"): 0.60,
    ("input_cost_shock", "third_party_failure"): 0.45,
    ("input_cost_shock", "inventory_stockout"): 0.40,
}


def _run(corr, n_sims=N_SIMS, seed=DEFAULT_SEED):
    draws = draw_copula_inputs(len(FIXTURE), n_sims, seed)
    freqs = frequency_draws(FIXTURE, n_sims, seed + 1)
    total, per = portfolio_losses(FIXTURE, freqs, uniforms_for(draws, corr))
    return total, per


# --------------------------------------------------------------------------
# Calibration
# --------------------------------------------------------------------------

def test_lognormal_from_range_recovers_inputs():
    """Solved (mu, sigma) must reproduce the mode and P90 it was fitted to."""
    for mode, p90 in [(450_000, 1_400_000), (800_000, 6_000_000), (80_000, 400_000)]:
        mu, sigma = lognormal_from_range(mode, p90)
        assert math.isclose(math.exp(mu - sigma**2), mode, rel_tol=1e-9)
        assert math.isclose(math.exp(mu + 1.2816 * sigma), p90, rel_tol=1e-9)


def test_lognormal_rejects_impossible_range():
    """A lognormal's P90 is always above its mode; reject the inverse loudly."""
    for bad in [(500_000, 500_000), (500_000, 400_000)]:
        try:
            lognormal_from_range(*bad)
            raise AssertionError(f"expected ValueError for {bad}")
        except ValueError:
            pass


def test_pert_mean_matches_simulation():
    """Closed-form PERT mean against its own sampler, with tolerance."""
    rng = np.random.default_rng(7)
    for lo, mode, hi in [(0.30, 0.80, 1.50), (0.05, 0.15, 0.40), (0.40, 1.00, 2.20)]:
        drawn = pert_samples(lo, mode, hi, 200_000, rng).mean()
        assert abs(drawn / pert_mean(lo, mode, hi) - 1) < 0.005


def test_closed_form_matches_simulation_50k():
    """THE calibration test. Tolerance, not equality: the closed form is exact
    but the simulation carries Monte Carlo noise (~0.1-0.3% at 50k)."""
    closed = closed_form_expected_loss(FIXTURE)
    corr = build_matrix(KEYS, PAIRS)
    total, _ = _run(corr)
    rel = abs(total.mean() / closed - 1)
    assert rel < CLOSED_FORM_TOL_50K, f"closed form {closed:,.0f} vs sim {total.mean():,.0f} ({rel:.4%})"


def test_closed_form_matches_simulation_10k():
    closed = closed_form_expected_loss(FIXTURE)
    total, _ = _run(build_matrix(KEYS, PAIRS), n_sims=10_000)
    assert abs(total.mean() / closed - 1) < CLOSED_FORM_TOL_10K


def test_expected_loss_is_invariant_to_correlation():
    """Expectation is linear, so dependence cannot move the mean. This is the
    honest headline: correlation changes the tail, never the average."""
    a, _ = _run(build_matrix(KEYS, PAIRS))
    b, _ = _run(build_matrix(KEYS, {}, baseline=0.0))
    assert abs(a.mean() / b.mean() - 1) < 0.01


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------

def test_determinism_byte_identical():
    corr = build_matrix(KEYS, PAIRS)
    for _ in range(2):
        t1, p1 = _run(corr)
        t2, p2 = _run(corr)
        assert np.array_equal(t1, t2)
        assert np.array_equal(p1, p2)


def test_shared_draws_isolate_dependence():
    """Two different matrices over the SAME draws must differ, and the same
    matrix over the same draws must be identical. This is what makes the
    robustness band measure dependence instead of sampling noise."""
    draws = draw_copula_inputs(len(FIXTURE), 20_000, DEFAULT_SEED)
    freqs = frequency_draws(FIXTURE, 20_000, DEFAULT_SEED + 1)
    base = build_matrix(KEYS, PAIRS)
    other = build_matrix(KEYS, PAIRS, baseline=0.5)

    t_a, _ = portfolio_losses(FIXTURE, freqs, uniforms_for(draws, base))
    t_a2, _ = portfolio_losses(FIXTURE, freqs, uniforms_for(draws, base))
    t_b, _ = portfolio_losses(FIXTURE, freqs, uniforms_for(draws, other))

    assert np.array_equal(t_a, t_a2)
    assert not np.array_equal(t_a, t_b)


def test_no_nan_and_non_negative():
    total, per = _run(build_matrix(KEYS, PAIRS))
    assert np.isfinite(total).all() and np.isfinite(per).all()
    assert (total >= 0).all() and (per >= 0).all()


def test_percentiles_ordered():
    total, _ = _run(build_matrix(KEYS, PAIRS))
    q = [np.percentile(total, p) for p in (50, 75, 90, 95, 99)]
    assert all(q[i] <= q[i + 1] for i in range(len(q) - 1))


# --------------------------------------------------------------------------
# Matrix validation and repair
# --------------------------------------------------------------------------

def test_build_matrix_shape_and_baseline():
    m = build_matrix(KEYS, PAIRS)
    assert m.shape == (6, 6)
    assert np.allclose(np.diag(m), 1.0)
    assert np.allclose(m, m.T)
    i, j = KEYS.index("third_party_failure"), KEYS.index("schedule_disruption")
    assert m[i, j] == 0.65
    # an unnamed pair falls back to the baseline
    k = KEYS.index("cyber_loss")
    assert m[i, k] == BASELINE_CORRELATION


def test_build_matrix_rejects_unknown_domain():
    try:
        build_matrix(KEYS, {("nope", "cyber_loss"): 0.4})
        raise AssertionError("expected KeyError")
    except KeyError:
        pass


def test_fixture_matrix_is_pd():
    require_pd(build_matrix(KEYS, PAIRS), "distribution")


def test_require_pd_fails_loudly():
    bad = np.array([[1.0, 0.95, -0.95], [0.95, 1.0, 0.95], [-0.95, 0.95, 1.0]])
    assert not is_pd(bad)
    try:
        require_pd(bad, "deliberately_broken")
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "not positive-definite" in str(e)


def test_ensure_pd_repairs_and_flags():
    bad = np.array([[1.0, 0.95, -0.95], [0.95, 1.0, 0.95], [-0.95, 0.95, 1.0]])
    fixed, repaired = ensure_pd(bad, "test")
    assert repaired and is_pd(fixed)
    assert np.allclose(np.diag(fixed), 1.0)
    good = build_matrix(KEYS, PAIRS)
    _, repaired2 = ensure_pd(good, "test")
    assert not repaired2


def test_perturbed_matrices_stay_pd():
    rng = np.random.default_rng(1)
    base = build_matrix(KEYS, PAIRS)
    for eps in (0.05, 0.10, 0.20):
        for _ in range(20):
            assert is_pd(perturbed_matrix(base, eps, rng))


def test_nearest_pd_is_identity_on_pd_input():
    good = build_matrix(KEYS, PAIRS)
    assert np.allclose(nearest_pd(good), good, atol=1e-8)


def test_independent_uniforms_are_independent():
    """The independent baseline must not reuse the shared chi-square, which is
    what creates t-copula tail dependence."""
    u = independent_uniforms(50_000, 6, 3)
    c = np.corrcoef(u.T)
    off = c[~np.eye(6, dtype=bool)]
    assert abs(off).max() < 0.02


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
