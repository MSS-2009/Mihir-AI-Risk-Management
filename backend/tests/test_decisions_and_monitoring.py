"""CP4 and CP5: decision templates, outcome tracking, and change detection."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from assessment import run_assessment  # noqa: E402
from connectors import FixtureProvider, PlantedTruth  # noqa: E402
from engines.decision_templates import (  # noqa: E402
    TEMPLATE_KINDS,
    DecisionTemplate,
    Option,
    evaluate_template,
)
from engines.decisions import Intervention  # noqa: E402
from industries import get_pack  # noqa: E402
from monitoring import Thresholds, compare_runs, detect_changes  # noqa: E402
from outcomes import MIN_SAMPLE_FOR_TRACK_RECORD, OutcomeStore  # noqa: E402


@pytest.fixture(scope="module")
def portfolio():
    pack = get_pack("industrial_distribution")
    corr, _ = pack.matrix()
    return pack.marginals(), corr


def _invest(**kw) -> DecisionTemplate:
    return DecisionTemplate(
        id="t", kind="invest_or_not", title="Qualify a second source",
        question="Should we dual-source?",
        options=[Option("do_it", "Qualify a second source", 180_000, 95_000,
                        [Intervention("third_party_failure", frequency=0.95, magnitude=0.55)])],
        **kw,
    )


# --------------------------------------------------------------------------
# Decision templates
# --------------------------------------------------------------------------

def test_every_template_kind_is_documented():
    from engines.decision_templates import KIND_DESCRIPTIONS
    assert set(KIND_DESCRIPTIONS) == set(TEMPLATE_KINDS)


def test_an_unknown_kind_is_refused(portfolio):
    """Four validated shapes, not a free-form box. A box that answers anything
    abandons the validated-model discipline that is the differentiator."""
    marginals, corr = portfolio
    with pytest.raises(ValueError):
        evaluate_template(
            DecisionTemplate("x", "ask_me_anything", "t", "q", [Option("a", "A")]),
            marginals, corr,
        )


def test_a_decision_with_no_options_is_refused(portfolio):
    marginals, corr = portfolio
    with pytest.raises(ValueError):
        evaluate_template(
            DecisionTemplate("x", "invest_or_not", "t", "q", []), marginals, corr
        )


def test_a_decision_reports_its_effect_on_the_risk_profile(portfolio):
    """The half no spreadsheet produces. NPV alone is a spreadsheet, and
    spreadsheets are free."""
    marginals, corr = portfolio
    out = evaluate_template(_invest(), marginals, corr)
    o = out["options"][0]

    assert "npv" in o and "npv_p10" in o and "npv_p90" in o
    assert o["p95_reduction"] > 0, "de-risking must reduce the tail"
    assert o["p99_reduction"] > 0
    assert out["verdict"]


def test_the_break_even_price_is_reported(portfolio):
    """'Not worth it' is a dead end; the price that would change it is not."""
    marginals, corr = portfolio
    out = evaluate_template(_invest(), marginals, corr)
    assert "break_even_annual_cost" in out
    assert out["break_even_annual_cost"] == pytest.approx(
        out["options"][0]["expected_saving_annual"]
        - out["options"][0]["cost_upfront"] / 2.486852, rel=1e-3
    )


def test_choosing_between_options_returns_probabilities_that_sum_to_one(portfolio):
    marginals, corr = portfolio
    t = DecisionTemplate(
        id="sourcing", kind="choose_between_options",
        title="How to de-risk", question="Which move?",
        options=[
            Option("dual", "Second source", 180_000, 95_000,
                   [Intervention("third_party_failure", frequency=0.95, magnitude=0.55)]),
            Option("buffer", "More inventory", 0, 240_000,
                   [Intervention("inventory_stockout", frequency=0.60, magnitude=0.85)]),
            Option("nothing", "Carry the exposure", 0, 0, []),
        ],
    )
    out = evaluate_template(t, marginals, corr)
    probs = [c["prob_best"] for c in out["comparison"]]
    assert sum(probs) == pytest.approx(1.0, abs=1e-6)
    assert all(c["expected_regret"] >= 0 for c in out["comparison"])
    assert out["recommended"]


def test_doing_nothing_wins_when_every_option_costs_more_than_it_saves(portfolio):
    """The product has to be able to say 'spend nothing'."""
    marginals, corr = portfolio
    t = DecisionTemplate(
        id="x", kind="choose_between_options", title="t", question="q",
        options=[
            Option("expensive", "Very expensive fix", 0, 5_000_000,
                   [Intervention("third_party_failure", frequency=0.9)]),
            Option("nothing", "Do nothing", 0, 0, []),
        ],
    )
    out = evaluate_template(t, marginals, corr)
    assert out["recommended"] == "nothing"


def test_templates_are_deterministic(portfolio):
    marginals, corr = portfolio
    a = evaluate_template(_invest(), marginals, corr)
    b = evaluate_template(_invest(), marginals, corr)
    assert a["options"][0]["npv"] == b["options"][0]["npv"]


# --------------------------------------------------------------------------
# Outcome tracking
# --------------------------------------------------------------------------

def test_the_full_predicted_distribution_is_stored_not_just_a_point():
    """A record of 'we said $140,000' cannot be scored: a prediction that put
    40% mass below zero was not wrong when the outcome was negative."""
    store = OutcomeStore()
    rec = store.record_presented("org1", {
        "id": "dual_source", "title": "Second source", "npv": 140_000,
        "npv_p10": -95_000, "npv_p90": 410_000, "prob_beneficial": 0.64,
        "cost_annual": 86_000, "p95_reduction": 312_000,
    }, snapshot_id="snap1")
    assert rec.predicted_npv_p10 == -95_000 and rec.predicted_npv_p90 == 410_000
    assert rec.prob_beneficial == 0.64
    assert rec.snapshot_id == "snap1"


def test_no_accuracy_claim_below_a_real_sample():
    """A hit rate on four decisions is the fastest way to lose a technical
    evaluator who asks how it was computed."""
    store = OutcomeStore()
    for i in range(4):
        r = store.record_presented("org1", {"id": f"d{i}", "npv": 1000,
                                            "npv_p10": 0, "npv_p90": 2000})
        store.mark(r.id, "taken")
        store.resolve(r.id, 1500)

    tr = store.track_record("org1")
    assert tr["available"] is False
    assert tr["resolved"] == 4
    assert str(MIN_SAMPLE_FOR_TRACK_RECORD) in tr["note"]
    assert "interval_coverage" not in tr


def test_track_record_measures_calibration_once_there_is_a_sample():
    store = OutcomeStore()
    for i in range(MIN_SAMPLE_FOR_TRACK_RECORD):
        r = store.record_presented("org1", {"id": f"d{i}", "npv": 1000,
                                            "npv_p10": 0, "npv_p90": 2000})
        store.resolve(r.id, 1500 if i % 2 == 0 else 5000)   # half inside

    tr = store.track_record("org1")
    assert tr["available"] is True
    assert tr["interval_coverage"] == pytest.approx(0.5, abs=0.01)
    assert tr["expected_coverage"] == 0.80


# --------------------------------------------------------------------------
# Change detection
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def two_runs():
    """The same customer, before and after a supply chain deteriorates."""
    pack = get_pack("industrial_distribution")
    answers = {q.id: q.default for q in pack.questions}
    quiet = FixtureProvider(profile="midmarket",
                            truth=PlantedTruth(late_delivery_rate=0.4)).build()
    bad = FixtureProvider(profile="midmarket",
                          truth=PlantedTruth(late_delivery_rate=2.6)).build()
    return (
        run_assessment("industrial_distribution", answers=answers, interpret=False, book=quiet),
        run_assessment("industrial_distribution", answers=answers, interpret=False, book=bad),
    )


def test_every_alert_states_a_cause(two_runs):
    """The rule the module exists to enforce. An alert without a cause is a
    notification, and notifications get muted."""
    before, after = two_runs
    result = compare_runs(before, after)
    assert result.material
    for c in result.changes:
        assert c.cause, f"{c.kind} has no cause"
        assert c.headline


def test_the_cause_names_the_parameter_that_moved(two_runs):
    before, after = two_runs
    changes = detect_changes(before, after)
    eal = next(c for c in changes if c.kind == "expected_annual_loss")
    assert "third party failure" in eal.cause
    assert "re-estimated" in eal.cause
    assert "observed" in eal.cause, "the cause should say how many events drove it"


def test_a_share_that_fell_only_because_others_grew_says_so(two_runs):
    """'Tariff shock down 14 points' reads as good news about a risk that did
    not improve. That is the most misleading thing this module could say."""
    before, after = two_runs
    fell = [c for c in detect_changes(before, after)
            if c.kind == "contribution" and (c.relative or 0) < 0]
    assert fell
    assert any("did not change" in c.cause for c in fell)


def test_identical_runs_produce_no_alert(two_runs):
    before, _ = two_runs
    assert compare_runs(before, before).changes == []
    assert not compare_runs(before, before).material


def test_thresholds_are_configurable(two_runs):
    before, after = two_runs
    loose = Thresholds(expected_annual_loss=5.0, tail_p95=5.0,
                       contribution_share=1.0, alert_on_provenance_change=False)
    assert detect_changes(before, after, loose) == []


def test_a_parameter_becoming_measured_is_itself_an_alert():
    """Crossing from our estimate to their data changes what the number means,
    which is worth telling someone even if the value barely moved."""
    pack = get_pack("industrial_distribution")
    answers = {q.id: q.default for q in pack.questions}
    unconnected = run_assessment("industrial_distribution", answers=answers, interpret=False,
                                 book=FixtureProvider(profile="sme").build())
    connected = run_assessment("industrial_distribution", answers=answers, interpret=False,
                               book=FixtureProvider(profile="midmarket").build())

    provenance = [c for c in detect_changes(unconnected, connected) if c.kind == "provenance"]
    assert provenance, "gaining a measured parameter should be reported"
    assert any("observations" in c.cause for c in provenance)
