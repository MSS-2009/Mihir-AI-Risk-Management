"""Model library tests: determinism and sanity bounds (spec §5.6).

Run:  python3 -m pytest backend/tests -q
      (or)  python3 backend/tests/test_models.py
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import MODEL_REGISTRY, run  # noqa: E402


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def _walk_numbers(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk_numbers(v)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield obj


def test_determinism():
    """Same inputs -> byte-identical outputs, every model, run twice."""
    for key in [k for k, s in MODEL_REGISTRY.items() if s.runnable]:
        a = json.dumps(run(key), sort_keys=True)
        b = json.dumps(run(key), sort_keys=True)
        assert a == b, f"{key} is non-deterministic"


def test_no_nan_or_inf():
    for key in [k for k, s in MODEL_REGISTRY.items() if s.runnable]:
        out = run(key)
        for n in _walk_numbers(out):
            assert math.isfinite(n), f"{key} produced non-finite value {n}"


def test_probabilities_in_unit_interval():
    for key in [k for k, s in MODEL_REGISTRY.items() if s.runnable]:
        out = run(key)
        for k, v in out.items():
            if any(t in k for t in ("prob", "probability", "_rate", "share")) and _finite(v):
                assert 0.0 <= v <= 1.0, f"{key}.{k} = {v} outside [0,1]"


def test_range_ordering():
    """Wherever a model reports a P10/P90 (or P90/P95) pair, they order correctly."""
    for key in [k for k, s in MODEL_REGISTRY.items() if s.runnable]:
        out = run(key)
        pairs = [
            ("net_savings_pv_p10", "net_savings_pv_p90"),
            ("gross_profit_p10", "gross_profit_p90"),
            ("revenue_p10", "revenue_p90"),
            ("pd_p10", "pd_p90"),
            ("loss_p90", "loss_p95"),
            ("cost_p90", "cost_p95"),
            ("loss_p95", "loss_p99"),
        ]
        for lo, hi in pairs:
            if lo in out and hi in out:
                assert out[lo] <= out[hi] + 1e-6, f"{key}: {lo} > {hi}"


def test_losses_non_negative():
    for key in [k for k, s in MODEL_REGISTRY.items() if s.runnable]:
        out = run(key)
        if "risk_summary" in out:
            rs = out["risk_summary"]
            assert rs["expected_loss"] >= 0, f"{key} expected_loss negative"
            assert rs["p95_loss"] >= 0, f"{key} p95_loss negative"
            assert rs["expected_loss"] <= rs["p95_loss"] + 1e-6, f"{key} expected>p95 loss"


def test_every_model_has_assumptions():
    """Rule §4.3: every model returns an explicit assumptions dict."""
    for key in [k for k, s in MODEL_REGISTRY.items() if s.runnable]:
        out = run(key)
        assert "assumptions" in out and isinstance(out["assumptions"], dict)
        assert out["assumptions"], f"{key} assumptions empty"


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
