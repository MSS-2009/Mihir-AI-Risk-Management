"""End-to-end assessment and API tests, on the no-API-key path.

Forcing client=None proves the whole product degrades to deterministic
narratives per industry, which is the guarantee that it never depends on a live
model to produce a number.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.pop("ANTHROPIC_API_KEY", None)
import llm  # noqa: E402

llm.client = None  # hard-disable AI for this module

from agents.portfolio import BANNED_CLAIMS, check_claims  # noqa: E402
from assessment import run_assessment, run_robustness  # noqa: E402
from industries import INDUSTRY_REGISTRY  # noqa: E402


def test_every_industry_assesses_without_api_key():
    for industry in INDUSTRY_REGISTRY:
        a = run_assessment(industry, interpret=True, include_sensitivity=True)
        assert a["expected_annual_loss"] > 0, industry
        assert a["interpretation"], industry
        assert a["recommendations"], industry
        assert a["sensitivity"], industry


def test_recommendations_always_carry_impact_and_range():
    """Never a bare 'you should': every action states what it is worth and how
    bad the bad case is."""
    for industry in INDUSTRY_REGISTRY:
        for r in run_assessment(industry, interpret=True, include_sensitivity=True)["recommendations"]:
            assert r["expected_annual_exposure"] > 0
            assert r["tail_exposure_p95"] >= r["expected_annual_exposure"]
            assert r["title"] and r["rationale"]


def test_recommendations_ranked():
    for industry in INDUSTRY_REGISTRY:
        recs = run_assessment(industry, interpret=True, include_sensitivity=True)["recommendations"]
        assert [r["rank"] for r in recs] == list(range(1, len(recs) + 1))
        tails = [r["tail_exposure_p95"] for r in recs]
        assert tails == sorted(tails, reverse=True)


def test_narrative_states_a_range_not_just_a_point():
    """Rule 4: never a point estimate without its range."""
    for industry in INDUSTRY_REGISTRY:
        text = run_assessment(industry, interpret=True, include_sensitivity=True)["interpretation"]
        assert "P95" in text and "P99" in text, industry


def test_narrative_makes_no_banned_claim():
    """The lint bans claim PATTERNS, not the word 'accurate', which the
    methodology page legitimately needs."""
    for industry in INDUSTRY_REGISTRY:
        a = run_assessment(industry, interpret=True, include_sensitivity=True)
        assert not check_claims(a["interpretation"]), industry
        for r in a["recommendations"]:
            assert not check_claims(r["rationale"] + r["title"]), industry


def test_copy_lint_catches_real_claims_but_allows_legitimate_use():
    assert check_claims("Based on industry data, this is typical.")
    assert check_claims("Our model is more accurate than the alternative.")
    # legitimate, must NOT trip
    assert not check_claims("Accuracy requires validation against realized losses.")
    assert not check_claims("These are starting estimates, not measured data.")


def test_intake_answers_actually_move_the_model():
    """A questionnaire whose answers change nothing would be theatre."""
    for industry, pack in INDUSTRY_REGISTRY.items():
        base = run_assessment(industry, interpret=False, include_sensitivity=False)
        # Modulation questions only. A derived question has no neutral answer:
        # its parameter is computed from the entities themselves rather than
        # multiplied around a default, so it is covered by the test below.
        neutral = {q.id: q.default for q in pack.questions if q.rule != "derived"}
        same = run_assessment(industry, answers=neutral, interpret=False, include_sensitivity=False)
        # accepting every default reproduces the published calibration exactly
        assert same["expected_annual_loss"] == base["expected_annual_loss"], industry
        # but a materially different answer must move it
        moved = dict(neutral)
        changed = False
        for q in pack.questions:
            if q.rule == "concentration" and isinstance(q.default, (int, float)):
                moved[q.id] = q.default * 1.8
                changed = True
                break
        if changed:
            alt = run_assessment(industry, answers=moved, interpret=False, include_sensitivity=False)
            assert alt["expected_annual_loss"] != base["expected_annual_loss"], industry
            assert alt["intake_adjustments"], industry


def test_derivation_layer_computes_from_the_operators_own_book():
    """The point of a deep pack: parameters come from the entities the operator
    entered, not from a multiplier they had to estimate themselves.

    Anything less and the pack is a generic calculator wearing an industry hat.
    """
    pack = INDUSTRY_REGISTRY["industrial_distribution"]
    derived_qs = [q for q in pack.questions if q.rule == "derived"]
    assert derived_qs, "the deep pack must have derived questions"

    base = run_assessment("industrial_distribution", interpret=False, include_sensitivity=False)
    answers = {q.id: q.default for q in pack.questions}
    deep = run_assessment("industrial_distribution", answers=answers,
                          interpret=False, include_sensitivity=False)

    # entities move the model, and by more than a rounding wobble
    assert deep["expected_annual_loss"] != base["expected_annual_loss"]
    assert abs(deep["expected_annual_loss"] / base["expected_annual_loss"] - 1) > 0.10

    # the derivation is reported, so a CFO can audit where the number came from
    facts = deep.get("derived_facts") or {}
    for key in ("hhi", "top_vendor", "sole_source_share", "annual_duty_cost",
                "blended_duty_rate", "weighted_days_of_cover", "top_site"):
        assert key in facts, key

    # and it is arithmetic on their book, not an opaque adjustment
    assert facts["annual_duty_cost"] > 0
    assert 0 < facts["hhi"] <= 1.0
    assert facts["top_vendor"] == "Jiangsu Machine Works"

    # decisions name the operator's own vendor and site rather than a placeholder
    titles = " | ".join(d["title"] for d in deep["decisions"])
    assert facts["top_vendor"] in titles
    assert facts["top_site"] in titles
    assert "{" not in titles, "an unfilled template leaked into a decision title"

    # deriving twice from the same book gives the same book
    again = run_assessment("industrial_distribution", answers=answers,
                           interpret=False, include_sensitivity=False)
    assert again["expected_annual_loss"] == deep["expected_annual_loss"]


def test_assessment_deterministic_without_key():
    import json
    for industry in ["clinical_research", "industrial_distribution"]:
        a = json.dumps(run_assessment(industry, interpret=True, include_sensitivity=True), sort_keys=True, default=str)
        b = json.dumps(run_assessment(industry, interpret=True, include_sensitivity=True), sort_keys=True, default=str)
        assert a == b, industry


def test_robustness_runs_for_every_industry_without_key():
    for industry in INDUSTRY_REGISTRY:
        r = run_robustness(industry, eps=0.10)
        assert r["robustness"]["p99_low"] <= r["robustness"]["p99_point"] <= r["robustness"]["p99_high"]
        assert r["dependence_fragility"]
        assert not check_claims(r["reading"]), industry


def test_every_industry_prices_its_decisions():
    """Decisions are the lead output, so every pack must produce them and every
    one must carry a cost, a saving with a range, and a probability."""
    for industry in INDUSTRY_REGISTRY:
        a = run_assessment(industry)
        assert a["decisions"], industry
        for d in a["decisions"]:
            assert d["cost_upfront"] + d["cost_annual"] > 0, industry
            assert d["saving_p10"] <= d["expected_saving_annual"] <= d["saving_p90"]
            assert 0.0 <= d["prob_beneficial"] <= 1.0
            assert d["npv_p10"] <= d["npv"] <= d["npv_p90"]


def test_decisions_ranked_by_npv():
    for industry in INDUSTRY_REGISTRY:
        npvs = [d["npv"] for d in run_assessment(industry)["decisions"]]
        assert npvs == sorted(npvs, reverse=True), industry


def test_a_null_decision_saves_nothing():
    """Common random numbers must make an intervention of 1.0x a true no-op,
    otherwise every reported saving is partly sampling noise."""
    from engines.decisions import Decision, Intervention, evaluate_decision
    from industries import get_pack
    pack = get_pack("industrial_distribution")
    corr, _ = pack.matrix()
    null = Decision(
        id="null", title="Do nothing", question="?", rationale="",
        interventions=[Intervention("cyber_loss", frequency=1.0, magnitude=1.0)],
    )
    r = evaluate_decision(pack.marginals(), corr, null)
    assert abs(r["expected_saving_annual"]) < 1e-6, r["expected_saving_annual"]


def test_decisions_deterministic():
    a = run_assessment("industrial_distribution")["decisions"]
    b = run_assessment("industrial_distribution")["decisions"]
    assert [x["npv"] for x in a] == [x["npv"] for x in b]


def test_api_surface():
    from starlette.testclient import TestClient
    from main import app

    c = TestClient(app)
    assert c.get("/").status_code == 200
    assert len(c.get("/industries").json()["industries"]) == 5
    m = c.get("/models").json()
    assert len(m["engines"]) == 11 and len(m["decision_models"]) == 2
    assert "starting estimate" in m["parameter_basis"].lower()
    assert c.post("/assess", json={"industry": "wealth_management"}).status_code == 200
    assert c.post("/assess", json={"industry": "nope"}).status_code == 404
    # the decision model kept per section 4.8 still works
    assert c.post("/analyze", json={"risk_type": "tariff"}).status_code == 200


def test_no_cross_industry_leakage():
    """A user in one industry must never be shown another industry's models."""
    names = {i: p.name for i, p in INDUSTRY_REGISTRY.items()}
    for industry in INDUSTRY_REGISTRY:
        text = run_assessment(industry, interpret=True, include_sensitivity=True)["interpretation"].lower()
        for other, other_name in names.items():
            if other == industry:
                continue
            assert other_name.lower() not in text, f"{industry} mentions {other_name}"


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
