"""End-to-end pipeline tests. These force the no-API-key path (client is None),
proving the whole graph + assessment degrade gracefully and deterministically.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force the no-key path before anything imports the client.
os.environ.pop("ANTHROPIC_API_KEY", None)
import llm  # noqa: E402
llm.client = None  # hard-disable AI for this module

from assessment import run_full_assessment  # noqa: E402
from domains import VALID_OUTPUT_FORMATS  # noqa: E402
from graph import GRAPH  # noqa: E402


def test_single_analyze_no_key():
    out = GRAPH.invoke({"risk_type": "tariff"})
    assert out["model_output"]["net_savings_pv_expected"] == 1909005.15
    assert out["interpretation"] and "range" in out["interpretation"].lower()
    assert out["trace"]["version"] == "1.0.0"


def test_full_assessment_no_key():
    a = run_full_assessment(output_format="executive_summary")
    assert a["composite"]["amplification_pct"] >= 0
    assert a["interpretation"]
    assert a["recommendations"] and a["recommendations"][0]["rank"] == 1
    # every recommendation carries a dollar impact AND a tail (range), never bare
    for r in a["recommendations"]:
        assert r["impact_expected"] is not None
        assert r["impact_tail"] is not None
    assert a["delivery"]["format"] == "executive_summary"
    assert a["delivery"]["key_numbers"]


def test_all_output_formats():
    for fmt in VALID_OUTPUT_FORMATS:
        a = run_full_assessment(output_format=fmt)
        assert a["delivery"]["format"] == fmt


def test_assessment_deterministic_no_key():
    import json
    a = json.dumps(run_full_assessment(), sort_keys=True, default=str)
    b = json.dumps(run_full_assessment(), sort_keys=True, default=str)
    assert a == b


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
