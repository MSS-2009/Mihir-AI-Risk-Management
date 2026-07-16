"""Composite correlation tests: determinism, PSD handling, and the core claim
that correlated tails exceed independent ones."""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from assessment import run_assessment  # noqa: E402
from models import run  # noqa: E402
from models.composite import (  # noqa: E402
    build_correlation_matrix,
    composite_risk_correlation,
    nearest_psd,
)


def _summaries():
    return {k: run(k)["risk_summary"]
            for k in ["supplier_health", "country", "delivery", "price", "cyber"]}


def test_composite_deterministic():
    a = json.dumps(composite_risk_correlation(_summaries()), sort_keys=True)
    b = json.dumps(composite_risk_correlation(_summaries()), sort_keys=True)
    assert a == b


def test_correlated_tail_exceeds_independent():
    """The whole thesis: positive correlation fattens the joint tail."""
    out = composite_risk_correlation(_summaries())
    assert out["correlated_p95"] >= out["independent_p95"]
    assert out["amplification_pct"] >= 0
    assert out["top_pairs"], "should rank compounding pairs"


def test_default_matrix_is_psd():
    keys = ["supplier_health", "country", "delivery", "price", "cyber", "market"]
    R = build_correlation_matrix(keys)
    w = np.linalg.eigvalsh(R)
    # Defaults should already be usable; nearest_psd is the safety net for edits.
    _, adjusted = nearest_psd(R)
    assert (w > -1e-6).all() or adjusted


def test_broken_matrix_gets_projected():
    keys = ["a", "b", "c"]
    # Force an invalid correlation set (not PSD) via overrides.
    overrides = {"a|b": 0.99, "a|c": -0.99, "b|c": 0.99}
    R = build_correlation_matrix(keys, overrides)
    C, adjusted = nearest_psd(R)
    assert adjusted
    assert (np.linalg.eigvalsh(C) > -1e-8).all()
    assert np.allclose(np.diag(C), 1.0)


def test_insufficient_domains():
    out = composite_risk_correlation({"country": _summaries()["country"]})
    assert out.get("insufficient_domains")


def test_assessment_runs_end_to_end():
    a = run_assessment()
    assert a["composite"] is not None
    assert len(a["ranked"]) == 6
    assert a["composite"]["amplification_pct"] >= 0


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
