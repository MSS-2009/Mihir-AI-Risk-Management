"""CP2: the parameter estimator.

The verification table from the specification is reproduced here, and then
extended. The published table contains only low-rate cases, and that is exactly
why the first reconstruction shipped a bug: none of its five cases pushes the
solved mode outside the bounds, so the clamp never bound and never showed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from connectors import FixtureProvider  # noqa: E402
from engines.fair import Marginal  # noqa: E402
from estimation import (  # noqa: E402
    estimate_frequency,
    estimate_frequency_triple,
    estimate_magnitude,
    estimate_marginals,
    observe_all,
    pert_mean,
)

# The distribution pack's third_party_failure triple, whose PERT mean is 0.4583
# and is the prior the specification's table is written against.
PRIOR_TRIPLE = (0.15, 0.40, 1.00)
PRIOR_MEAN = pert_mean(PRIOR_TRIPLE)


def test_prior_mean_matches_the_specification():
    assert PRIOR_MEAN == pytest.approx(0.458, abs=0.001)


# --------------------------------------------------------------------------
# The published verification table (spec Part 6.2)
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "n_events,years,mean,ci_lo,ci_hi,weight",
    [
        (0, 0, 0.458, 0.05, 1.23, 0.00),
        (0, 1, 0.344, 0.03, 0.92, 0.25),
        (1, 2, 0.475, 0.10, 1.07, 0.40),
        (12, 5, 1.672, 1.00, 2.49, 0.62),
        (4, 10, 0.413, 0.17, 0.74, 0.77),
    ],
)
def test_published_verification_table(n_events, years, mean, ci_lo, ci_hi, weight):
    p = estimate_frequency(PRIOR_MEAN, n_events, years)
    assert p.mean == pytest.approx(mean, abs=0.001)
    assert p.ci_low == pytest.approx(ci_lo, abs=0.006)
    assert p.ci_high == pytest.approx(ci_hi, abs=0.006)
    assert p.weight_on_data == pytest.approx(weight, abs=0.006)


def test_required_properties_of_the_posterior():
    assert estimate_frequency(PRIOR_MEAN, 0, 0).mean == pytest.approx(PRIOR_MEAN, abs=1e-12)

    # always between prior and naive rate
    for n, y in [(0, 1), (1, 2), (12, 5), (4, 10), (25, 2)]:
        p = estimate_frequency(PRIOR_MEAN, n, y)
        assert min(PRIOR_MEAN, p.naive_rate) - 1e-9 <= p.mean <= max(PRIOR_MEAN, p.naive_rate) + 1e-9

    # converges toward the naive rate as evidence accumulates
    far = estimate_frequency(PRIOR_MEAN, 240, 60)
    assert far.mean == pytest.approx(240 / 60, rel=0.06)

    # The interval narrows monotonically with observation, at a FIXED rate.
    # The rate has to be held constant to say anything: a higher rate widens the
    # absolute interval, so varying both the window and the event count compares
    # two things at once and the property appears to fail when it has not.
    widths = [
        (lambda p: p.ci_high - p.ci_low)(estimate_frequency(PRIOR_MEAN, y // 2, y))
        for y in (2, 4, 10, 20, 40)      # naive rate is exactly 0.5 throughout
    ]
    assert widths == sorted(widths, reverse=True), widths


# --------------------------------------------------------------------------
# PERT reconstruction. The mean-matching identity is the whole contract.
# --------------------------------------------------------------------------

HIGH_RATE_CASES = [
    (5, 0.5), (12, 1), (25, 2), (50, 2), (200, 0.5),   # these bind the bounds
    (3, 0.25), (40, 1), (100, 1),
]
LOW_RATE_CASES = [(0, 0), (0, 1), (1, 2), (12, 5), (4, 10), (2, 3), (0, 5)]


@pytest.mark.parametrize("n_events,years", LOW_RATE_CASES + HIGH_RATE_CASES)
def test_pert_triple_mean_equals_the_posterior_mean(n_events, years):
    """The identity the reconstruction exists to guarantee.

    Asserting the identity rather than hand-copied expected values is deliberate:
    a hand-copied table is only as good as the cases someone thought to include,
    and the clamp bug survived precisely because the published cases were all
    well-behaved.
    """
    triple, posterior = estimate_frequency_triple(PRIOR_TRIPLE, n_events, years)
    assert pert_mean(triple) == pytest.approx(posterior.mean, rel=1e-9)


@pytest.mark.parametrize("n_events,years", HIGH_RATE_CASES)
def test_high_rate_cases_are_not_understated(n_events, years):
    """The regression for the clamp bug.

    Clamping the mode into the bounds silently discarded the mean-matching
    property: across a 55-case sweep 26 hit the clamp, and every one understated,
    by 38% at five failures in six months and 83% at the extreme. Understating
    frequency is the worst direction for a risk product to be wrong in, so this
    asserts the reconstruction never lands low.
    """
    triple, posterior = estimate_frequency_triple(PRIOR_TRIPLE, n_events, years)
    assert pert_mean(triple) >= posterior.mean * (1 - 1e-9), (
        f"reconstruction understated: {pert_mean(triple)} < {posterior.mean}"
    )


def test_triple_stays_ordered_and_non_negative():
    for n, y in LOW_RATE_CASES + HIGH_RATE_CASES:
        lo, mode, hi = estimate_frequency_triple(PRIOR_TRIPLE, n, y)[0]
        assert lo >= 0.0
        assert lo <= mode <= hi, f"unordered triple at n={n}, years={y}: {(lo, mode, hi)}"


def test_zero_data_returns_the_pack_triple_exactly():
    """The guarantee the entire design rests on: connecting a system that
    carries no relevant history must not move a single number."""
    triple, posterior = estimate_frequency_triple(PRIOR_TRIPLE, 0, 0)
    assert triple == pytest.approx(PRIOR_TRIPLE, abs=1e-12)
    assert posterior.weight_on_data == 0.0


# --------------------------------------------------------------------------
# Magnitude
# --------------------------------------------------------------------------

def test_magnitude_with_no_observations_returns_the_prior():
    p = estimate_magnitude(prior_mu=12.0, prior_sigma=0.9, observed_losses=[])
    assert p.mu == 12.0 and p.sigma == 0.9 and p.weight_on_data == 0.0


def test_magnitude_shrinks_toward_the_prior():
    import math
    losses = [math.exp(13.0)] * 5
    p = estimate_magnitude(prior_mu=12.0, prior_sigma=0.9, observed_losses=losses)
    assert 12.0 < p.mu < 13.0
    assert p.weight_on_data == pytest.approx(5 / 10)


def test_dispersion_is_held_until_there_is_enough_to_estimate_it():
    """Under-observed sigma is the fastest route to an understated tail."""
    import math
    few = estimate_magnitude(12.0, 0.9, [math.exp(12 + 0.01 * i) for i in range(6)])
    assert few.sigma_is_prior and few.sigma == 0.9

    many = estimate_magnitude(12.0, 0.9, [math.exp(12 + (i % 7)) for i in range(40)])
    assert not many.sigma_is_prior and many.sigma > 0.9


def test_dispersion_never_narrows_below_the_published_prior():
    import math
    tight = estimate_magnitude(12.0, 1.4, [math.exp(12.0)] * 40)
    assert tight.sigma == 1.4, "a tight sample must not shrink the tail"


# --------------------------------------------------------------------------
# End to end against the fixture
# --------------------------------------------------------------------------

def test_no_book_is_a_no_op():
    """Unconnected assessments must be byte-identical to v2."""
    m = [Marginal("third_party_failure", "Vendor failure", (0.15, 0.40, 1.00), (250_000, 900_000))]
    result = estimate_marginals(m, None)
    assert result.marginals == m
    assert result.estimates == []


def test_estimator_recovers_the_planted_failure_rate():
    """Correctness, not regression: the fixture planted a rate and the estimator
    has to find it, shrunk toward the prior by the observation window."""
    p = FixtureProvider(profile="midmarket")
    book = p.build()
    obs = observe_all(book)["third_party_failure"]

    assert obs.available
    assert obs.n_events == p.truth.n_late

    _triple, posterior = estimate_frequency_triple(
        PRIOR_TRIPLE, obs.n_events, obs.years_observed
    )
    naive = obs.n_events / obs.years_observed
    assert min(PRIOR_MEAN, naive) <= posterior.mean <= max(PRIOR_MEAN, naive)
    assert 0.4 < posterior.weight_on_data < 0.6, "3 years against a 3-year prior is ~50%"


def test_a_thin_connection_measures_nothing_and_says_why():
    """The distinction that keeps the claim honest: absent is not empty."""
    book = FixtureProvider(profile="sme").build()
    obs = observe_all(book)

    tpf = obs["third_party_failure"]
    assert not tpf.available
    assert "promise date" in tpf.reason
    assert obs["inventory_stockout"].available is False

    # and the customer-side measurement still works on the same thin connection
    assert obs["counterparty_concentration"].available


def test_thin_connection_leaves_every_marginal_untouched_where_unmeasured():
    from industries import get_pack

    pack = get_pack("industrial_distribution")
    marginals = pack.marginals()
    book = FixtureProvider(profile="sme").build()
    result = estimate_marginals(marginals, book)

    by_key = {m.key: m for m in result.marginals}
    for original in marginals:
        if original.key == "counterparty_concentration":
            continue                    # this one is genuinely measurable
        if original.key in ("schedule_disruption",):
            continue                    # lead-time dispersion fallback applies
        assert by_key[original.key].lef == original.lef, original.key


def test_coverage_counts_parameters_not_engines():
    """An engine with a measured frequency and a prior magnitude is half
    measured; reporting it as measured would overstate the product."""
    from industries import get_pack

    book = FixtureProvider(profile="midmarket").build()
    result = estimate_marginals(get_pack("industrial_distribution").marginals(), book)
    cov = result.coverage

    assert cov["total"] == 12, "6 engines x 2 parameters for this pack"
    assert cov["measured"] + cov["blended"] + cov["prior"] == cov["total"]
    assert cov["prior"] > 0, "finance data cannot speak to cyber, recall or compliance"
    assert any("not visible in financial records" in u for u in cov["unlocks"])


def test_estimation_is_deterministic():
    from industries import get_pack

    pack = get_pack("industrial_distribution")
    a = estimate_marginals(pack.marginals(), FixtureProvider(profile="midmarket").build())
    b = estimate_marginals(pack.marginals(), FixtureProvider(profile="midmarket").build())
    assert [m.lef for m in a.marginals] == [m.lef for m in b.marginals]
    assert [e.public() for e in a.estimates] == [e.public() for e in b.estimates]


# --------------------------------------------------------------------------
# CP3: the estimator inside the assessment pipeline
# --------------------------------------------------------------------------

def test_an_unconnected_assessment_is_byte_identical_to_v2():
    """The guarantee the whole layering rests on.

    Connected data changes where parameters come from, never how engines
    behave. If this drifts, every v2 number a customer has seen becomes wrong.
    """
    import json
    from assessment import run_assessment
    from industries import INDUSTRY_REGISTRY

    for industry, pack in INDUSTRY_REGISTRY.items():
        answers = {q.id: q.default for q in pack.questions}
        a = run_assessment(industry, answers=answers, interpret=False, include_sensitivity=False)
        b = run_assessment(industry, answers=answers, interpret=False,
                           include_sensitivity=False, book=None)
        assert json.dumps(a, sort_keys=True, default=str) == \
               json.dumps(b, sort_keys=True, default=str), industry
        assert a["estimation"] is None, "no book means no estimation block"


def test_measurement_damps_the_intake_multiplier():
    """Intake and a measurement can describe the same fact.

    A vendor-failure rate estimated from purchase orders already contains the
    concentration the operator typed into intake, so applying both at full
    strength counts one fact twice. The multiplier fades by weight_on_data.
    """
    from engines.modulation import Modulation, damped

    mod = Modulation(frequency=1.6, magnitude=1.4)
    assert damped(mod, 1.0) == mod                       # nothing measured
    half = damped(mod, 0.5)
    assert half.frequency == pytest.approx(1.3)          # halfway to neutral
    assert half.magnitude == pytest.approx(1.2)
    full = damped(mod, 0.0)                              # fully measured
    assert full.frequency == 1.0 and full.magnitude == 1.0


def test_connected_run_reports_provenance_for_every_parameter():
    from assessment import run_assessment
    from industries import get_pack

    pack = get_pack("industrial_distribution")
    answers = {q.id: q.default for q in pack.questions}
    book = FixtureProvider(profile="midmarket").build()
    out = run_assessment("industrial_distribution", answers=answers,
                         interpret=False, book=book)

    est = out["estimation"]
    assert est is not None
    assert est["coverage"]["total"] == len(pack.bindings) * 2
    for p in est["parameters"]:
        assert p["provenance"] in ("measured", "blended", "prior")
        if p["provenance"] == "prior":
            assert p["reason"], f"a prior must say why: {p['engine']}/{p['parameter']}"
    assert est["snapshot"]["snapshot_id"]


def test_a_thin_connection_moves_less_than_a_rich_one():
    """Coverage should reward connecting more, which is the whole incentive."""
    from assessment import run_assessment
    from industries import get_pack

    answers = {q.id: q.default for q in get_pack("industrial_distribution").questions}
    thin = run_assessment("industrial_distribution", answers=answers, interpret=False,
                          book=FixtureProvider(profile="sme").build())
    rich = run_assessment("industrial_distribution", answers=answers, interpret=False,
                          book=FixtureProvider(profile="midmarket").build())

    thin_known = thin["estimation"]["coverage"]["measured"] + thin["estimation"]["coverage"]["blended"]
    rich_known = rich["estimation"]["coverage"]["measured"] + rich["estimation"]["coverage"]["blended"]
    assert rich_known > thin_known


def test_a_single_snapshot_never_evidences_a_rate_over_time():
    """Inventory levels on one day are an instant, not a history.

    Counting SKUs at zero and dividing by the observation window would let a
    book that happened to be well stocked on sync day earn a reduction it never
    demonstrated.
    """
    book = FixtureProvider(profile="midmarket").build()
    obs = observe_all(book)
    assert not obs["inventory_stockout"].available
    assert "single instant" in obs["inventory_stockout"].reason
    assert not obs["input_cost_shock"].available
