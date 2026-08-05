"""Robustness band and dependence fragility (the 4.10 layer).

The band is only meaningful if the Monte Carlo draws are held fixed across
perturbations, so that is tested directly rather than assumed.
"""
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engines.constants import N_SIMS_SWEEP  # noqa: E402
from engines.copula import draw_copula_inputs, perturbed_matrix  # noqa: E402
from engines.composite import run_portfolio  # noqa: E402
from engines.fair import frequency_draws  # noqa: E402
from engines.robustness import (  # noqa: E402
    EPS_LEVELS,
    dependence_fragility,
    robustness_assessment,
    robustness_band,
)
from industries import INDUSTRY_REGISTRY, get_pack  # noqa: E402

PACK = get_pack("industrial_distribution")
MARGINALS = PACK.marginals()
CORR, _ = PACK.matrix()

# Structural properties hold at any sample size. Run them small to keep the
# suite fast; the reference test below runs at the pinned settings.
FAST = {"n_draws": 15, "n_sims": 20_000}
FAST_FR = {"n_sims": 20_000}


def test_band_brackets_the_point_estimate():
    b = robustness_band(MARGINALS, CORR, eps=0.10, **FAST)
    assert b["p99_low"] <= b["p99_point"] <= b["p99_high"]
    assert b["p95_low"] <= b["p95_point"] <= b["p95_high"]


def test_band_widens_with_eps():
    """More dependence uncertainty must produce a wider envelope."""
    spreads = [robustness_band(MARGINALS, CORR, eps=e, **FAST)["p99_spread_pct"] for e in (0.05, 0.10, 0.20)]
    assert spreads[0] < spreads[1] < spreads[2], spreads


def test_band_is_reassuring_at_moderate_eps():
    """A tight band at eps=0.10 is a real finding and the product says so.
    If this ever exceeds ~15% the honest reading flips to 'sensitive'."""
    b = robustness_band(MARGINALS, CORR, eps=0.10)
    assert 0.0 < b["p99_spread_pct"] < 0.15, b["p99_spread_pct"]


def test_fixed_draws_isolate_dependence():
    """THE correctness property. Same matrix + same draws must be identical;
    a different matrix over the same draws must differ. If the draws were
    re-randomised per perturbation the band would measure sampling noise."""
    draws = draw_copula_inputs(len(MARGINALS), 20_000, 42)
    freqs = frequency_draws(MARGINALS, 20_000, 43)
    rng = np.random.default_rng(7)
    m1 = perturbed_matrix(CORR, 0.10, rng)
    a = run_portfolio(MARGINALS, m1, draws, freqs).pct(99)
    b = run_portfolio(MARGINALS, m1, draws, freqs).pct(99)
    c = run_portfolio(MARGINALS, perturbed_matrix(CORR, 0.10, rng), draws, freqs).pct(99)
    assert a == b
    assert a != c


def test_band_deterministic():
    a = robustness_band(MARGINALS, CORR, eps=0.10, **FAST)
    b = robustness_band(MARGINALS, CORR, eps=0.10, **FAST)
    assert a == b


def test_band_deterministic_across_processes():
    """Guards the BLAS finding: multithreaded matmul can change reduction order
    and silently break reproducibility. Determinism must hold across a fresh
    interpreter, not just within one."""
    code = (
        "import sys; sys.path.insert(0,'.');"
        "from industries import get_pack;"
        "from engines.robustness import robustness_band;"
        "p=get_pack('industrial_distribution'); c,_=p.matrix();"
        "b=robustness_band(p.marginals(), c, eps=0.10, n_draws=8, n_sims=20000);"
        "print(f\"{b['p99_low']:.6f}|{b['p99_high']:.6f}\")"
    )
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outs = set()
    for _ in range(2):
        r = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-800:]
        outs.add(r.stdout.strip().splitlines()[-1])
    assert len(outs) == 1, f"non-deterministic across processes: {outs}"


def test_fragility_ranked_and_complete():
    fr = dependence_fragility(MARGINALS, CORR, **FAST_FR)
    d = len(MARGINALS)
    assert len(fr) == d * (d - 1) // 2
    swings = [f["p99_swing"] for f in fr]
    assert swings == sorted(swings, reverse=True)
    assert all(s >= 0 for s in swings)


def test_fragility_top_pair_is_stable():
    """The ranking is the product output, so it must not move between runs."""
    a = dependence_fragility(MARGINALS, CORR, **FAST_FR)[0]
    b = dependence_fragility(MARGINALS, CORR, **FAST_FR)[0]
    assert a["pair"] == b["pair"] and a["p99_swing"] == b["p99_swing"]


def test_fragility_flags_default_pairs():
    """A pair still sitting at the 0.20 baseline is exactly where refinement
    pays, so it has to be identifiable in the output."""
    fr = dependence_fragility(MARGINALS, CORR, **FAST_FR)
    assert any(f["is_default"] for f in fr)
    for f in fr:
        assert f["is_default"] == (abs(f["rho"] - 0.20) < 1e-9)


def test_assessment_shape_and_reading():
    ra = robustness_assessment(MARGINALS, CORR, n_sims=20_000)
    assert set(ra) == {"robustness", "dependence_fragility", "eps_levels", "reading"}
    assert ra["eps_levels"] == EPS_LEVELS
    r = ra["reading"]
    assert "robust" in r or "sensitive" in r
    # never claim accuracy
    for banned in ("more accurate", "proven accuracy", "industry benchmark", "based on industry data"):
        assert banned not in r.lower()


def test_reference_band_at_pinned_settings():
    """Full-fidelity reference. Slow by design: this is the number we publish."""
    b = robustness_band(MARGINALS, CORR, eps=0.10)
    assert b["n_sims"] == N_SIMS_SWEEP and b["n_draws"] == 60
    assert 0.03 < b["p99_spread_pct"] < 0.12
    assert b["p99_low"] <= b["p99_point"] <= b["p99_high"]


def test_sweep_runs_at_pinned_n_sims():
    assert robustness_band(MARGINALS, CORR)["n_sims"] == N_SIMS_SWEEP


def test_all_industries_have_a_band():
    for industry in INDUSTRY_REGISTRY:
        p = get_pack(industry)
        c, _ = p.matrix()
        b = robustness_band(p.marginals(), c, eps=0.10, n_draws=12)
        assert b["p99_low"] <= b["p99_point"] <= b["p99_high"], industry


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
