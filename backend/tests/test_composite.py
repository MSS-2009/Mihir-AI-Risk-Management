"""Composite portfolio tests and the pinned regression targets.

Tolerance discipline, which matters more here than anywhere else in the suite:

  Expected annual loss is STABLE (varies ~0.03% across implementation variants),
  so it is tested tightly at 0.2%.

  Tail percentiles are NOT stable better than ~3%, because estimating a 1-in-100
  point from 50,000 draws is inherently noisy. They are tested at 3%. That is a
  property of tail estimation, not a defect, and tightening it would only
  generate phantom failures.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engines.composite import composite_risk_correlation, run_portfolio  # noqa: E402
from engines.constants import (  # noqa: E402
    DEFAULT_SEED,
    EAL_REGRESSION_TOL,
    N_SIMS,
    TAIL_REGRESSION_TOL,
)
from engines.copula import draw_copula_inputs, is_pd  # noqa: E402
from engines.fair import closed_form_expected_loss, frequency_draws  # noqa: E402
from industries import INDUSTRY_REGISTRY, get_pack  # noqa: E402

# Pinned at n_sims=50,000 with the section 2.6 text matrix (4 named pairs over a
# 0.20 baseline). These supersede the spec's 2.5 and 4.10.3 tables.
TARGETS = {
    "industrial_distribution": {"eal": 1_884_905, "p99": 5_648_970},
}


def _assess(industry: str, **kw):
    pack = get_pack(industry)
    corr, repaired = pack.matrix()
    return composite_risk_correlation(pack.marginals(), corr, pack.id, matrix_repaired=repaired, **kw)


def _pct(out, p):
    return next(e["loss"] for e in out["exceedance_curve"] if e["percentile"] == p)


def test_distribution_expected_loss_regression():
    """EAL is the stable target. Tight tolerance."""
    out = _assess("industrial_distribution")
    t = TARGETS["industrial_distribution"]["eal"]
    rel = abs(out["expected_annual_loss"] / t - 1)
    assert rel < EAL_REGRESSION_TOL, f"EAL {out['expected_annual_loss']:,.0f} vs {t:,.0f} ({rel:.3%})"


def test_distribution_p99_regression():
    """P99 is not stable better than ~3%. Loose tolerance, deliberately."""
    out = _assess("industrial_distribution")
    t = TARGETS["industrial_distribution"]["p99"]
    rel = abs(_pct(out, 99) / t - 1)
    assert rel < TAIL_REGRESSION_TOL, f"P99 {_pct(out, 99):,.0f} vs {t:,.0f} ({rel:.3%})"


def test_closed_form_agrees_with_simulated_eal():
    out = _assess("industrial_distribution")
    rel = abs(out["expected_annual_loss"] / out["expected_annual_loss_closed_form"] - 1)
    assert rel < 0.005


def test_correlation_premium_non_negative_at_p99():
    """A negative premium means the headline metric is computed wrong, most
    likely by comparing against a sum of standalone percentiles."""
    for industry in INDUSTRY_REGISTRY:
        out = _assess(industry)
        assert out["correlation_premium"]["p99"] >= 0, industry
        assert out["correlation_premium"]["p95"] >= 0, industry


def test_correlation_does_not_move_the_mean():
    """Expectation is linear. State this plainly rather than hiding it."""
    for industry in INDUSTRY_REGISTRY:
        out = _assess(industry)
        rel = abs(out["expected_annual_loss"] / out["expected_annual_loss_independent"] - 1)
        assert rel < 0.01, f"{industry}: correlation moved the mean by {rel:.2%}"


def test_joint_breach_exceeds_independent():
    for industry in INDUSTRY_REGISTRY:
        jb = _assess(industry)["joint_breach"]
        assert jb["three_plus"] > jb["three_plus_independent"], industry
        assert 0.0 <= jb["three_plus"] <= 1.0 and 0.0 <= jb["two_plus"] <= 1.0


def test_exceedance_curve_monotonic():
    for industry in INDUSTRY_REGISTRY:
        losses = [e["loss"] for e in _assess(industry)["exceedance_curve"]]
        assert all(losses[i] <= losses[i + 1] for i in range(len(losses) - 1)), industry


def test_all_packs_positive_definite():
    """Authored pack matrices must be PD. pack.matrix() raises loudly if not."""
    for industry, pack in INDUSTRY_REGISTRY.items():
        corr, repaired = pack.matrix()
        assert is_pd(corr), industry
        assert not repaired, f"{industry} authored matrix needed repair; fix the pairs"


def test_determinism():
    a = _assess("industrial_distribution")
    b = _assess("industrial_distribution")
    assert a["expected_annual_loss"] == b["expected_annual_loss"]
    assert a["exceedance_curve"] == b["exceedance_curve"]
    assert a["joint_breach"] == b["joint_breach"]


def test_assumptions_reproduce_the_run():
    """The assumptions block must be sufficient to rebuild the run exactly."""
    out = _assess("industrial_distribution")
    a = out["assumptions"]
    assert a["n_sims"] == N_SIMS and a["seed"] == DEFAULT_SEED
    assert a["copula"]["df"] == 4 and a["copula"]["applied_to"] == "magnitude"
    m = a["correlation_matrix"]
    assert len(m["matrix"]) == len(m["keys"]) == len(out["assumptions"]["domains"])
    for dom in a["domains"]:
        assert {"lef_min", "lef_mode", "lef_max", "magnitude_mode", "magnitude_p90", "mu", "sigma"} <= dom.keys()
    assert "expert judgment" in a["parameter_basis"]


def test_domain_contributions_sum_to_one():
    for industry in INDUSTRY_REGISTRY:
        dc = _assess(industry)["domain_contributions"]
        assert abs(sum(d["base_share"] for d in dc) - 1.0) < 0.01
        assert abs(sum(d["tail_share"] for d in dc) - 1.0) < 0.01


def test_revenue_scaling_is_proportional():
    """alpha=1.0: doubling revenue doubles expected loss, so loss stays a
    constant share of revenue. Exposed as a parameter so sublinear scaling
    later is a config change."""
    pack = get_pack("industrial_distribution")
    base = closed_form_expected_loss(pack.marginals())
    dbl = closed_form_expected_loss(pack.marginals(revenue=pack.reference_revenue * 2))
    assert abs(dbl / base - 2.0) < 1e-9
    sub = closed_form_expected_loss(pack.marginals(revenue=pack.reference_revenue * 2, alpha=0.7))
    assert sub < dbl


def test_engines_do_not_import_industries():
    """The one-way dependency rule that keeps a sixth industry a data change."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent / "engines"
    for f in root.glob("*.py"):
        src = f.read_text()
        assert "from industries" not in src and "import industries" not in src, f.name


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
