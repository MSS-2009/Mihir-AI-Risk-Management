"""Assessment orchestration: industry pack in, dashboard payload out.

Split deliberately into two calls:

  run_assessment   composite + sensitivity. Fast (~2.5s), blocks the dashboard.
  run_robustness   the 4.10 dependence layer. ~5s, loaded after the dashboard
                   paints rather than holding it hostage.

The split is a measurement, not a guess: the composite is 90ms, but the
robustness sweep needs ~90 sequential portfolio runs at the pinned sample size,
and the fragility ranking is unstable at smaller samples.
"""
from __future__ import annotations

from canonical import Book
from engines.composite import composite_risk_correlation
from engines.decisions import rank_decisions
from engines.constants import DEFAULT_SEED, N_SIMS
from engines.modulation import apply_modulations, damped
from engines.robustness import DEFAULT_EPS, robustness_assessment
from agents.portfolio import build_recommendations, portfolio_interpretation
from engines.sensitivity import sensitivity
from estimation import estimate_marginals
from industries import get_pack

REVENUE_QUESTION = "annual_revenue"


def _fmt_facts(facts: dict) -> dict:
    """Presentation-ready variants so a decision template can interpolate a
    fact without the pack having to know about formatting."""
    out = dict(facts)
    for k, v in list(facts.items()):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[f"{k}_int"] = f"{v:,.0f}"
            out[f"{k}_money"] = f"${v:,.0f}"
            out[f"{k}_pct"] = f"{v:.0%}" if abs(v) <= 1 else f"{v:.1f}"
    return out


def _personalise(decisions: list, facts: dict) -> list:
    """Fill decision templates with the operator's own entities.

    'Qualify a second source for Jiangsu Machine Works' lands very differently
    from 'qualify a second source for your largest vendor'.
    """
    if not facts:
        return decisions
    f = _fmt_facts(facts)
    out = []
    for d in decisions:
        try:
            out.append(
                type(d)(
                    id=d.id,
                    title=d.title.format_map(_Safe(f)),
                    question=d.question.format_map(_Safe(f)),
                    rationale=d.rationale.format_map(_Safe(f)),
                    interventions=d.interventions,
                    cost_upfront=d.cost_upfront,
                    cost_annual=d.cost_annual,
                    effort=d.effort,
                    reversible=d.reversible,
                )
            )
        except Exception:
            out.append(d)
    return out


class _Safe(dict):
    """Leaves an unknown placeholder as readable text rather than raising."""

    def __missing__(self, key):
        return "your book"


def _apply_costs(decisions: list, overrides: dict | None, revenue_scale: float) -> list:
    """Replace pack cost estimates with what the operator says it costs them.

    The first thing a prospect pushes back on is the price tag, and a number
    they cannot change is one they will argue with instead of acting on. Costs
    arrive in the units shown on screen, which are already revenue-scaled, so
    they are converted back to reference scale here and scaled forward again by
    the evaluator. That keeps one definition of the scaling rather than two.
    """
    if not overrides:
        return decisions
    scale = revenue_scale or 1.0
    out = []
    for d in decisions:
        o = overrides.get(d.id)
        if not o:
            out.append(d)
            continue
        up = o.get("cost_upfront")
        yr = o.get("cost_annual")
        out.append(
            type(d)(
                id=d.id, title=d.title, question=d.question, rationale=d.rationale,
                interventions=d.interventions,
                cost_upfront=(float(up) / scale) if up is not None else d.cost_upfront,
                cost_annual=(float(yr) / scale) if yr is not None else d.cost_annual,
                effort=d.effort, reversible=d.reversible,
            )
        )
    return out


def _prepare(
    industry: str,
    answers: dict | None,
    correlation_overrides: dict | None,
    alpha: float,
    book: Book | None = None,
):
    """Resolve a pack, connected history and intake answers into marginals.

    Three layers, in this order and for a reason.

    The estimator goes first because it sets parameters absolutely from observed
    history, while intake and entity derivation are multipliers on top of a
    starting estimate. Running them the other way round would multiply a
    measurement by a guess about the same thing.

    Intake and derivation then apply, damped by how much of each parameter the
    measurement already explains. A vendor-failure rate estimated from purchase
    orders already contains the concentration the operator described in intake,
    so applying both at full strength counts one fact twice.

    With `book=None` nothing above fires and this is byte-for-byte the v2 path,
    which is the guarantee the pinned regression enforces.
    """
    pack = get_pack(industry)
    answers = answers or {}
    revenue = answers.get(REVENUE_QUESTION) or pack.reference_revenue
    marginals = pack.marginals(revenue=revenue, alpha=alpha)

    estimation = estimate_marginals(marginals, book)
    marginals = estimation.marginals
    # How much of an intake answer survives, per engine: all of it when nothing
    # was measured, none of it when the measurement is authoritative.
    damping = {
        e.engine: 1.0 - e.weight_on_data
        for e in estimation.estimates if e.parameter == "frequency"
    }

    marginals, trail = apply_modulations(marginals, answers, pack.questions, damping)

    # A deep pack derives parameters from the operator's own entities.
    facts: dict = {}
    if callable(getattr(pack, "derive", None)):
        facts, derived_trail = pack.derive(answers, marginals)
        mods = facts.pop("_modulations", {}) if facts else {}
        if mods:
            mods = {k: damped(v, damping.get(k, 1.0)) for k, v in mods.items()}
            marginals = [
                m if m.key not in mods else type(m)(
                    key=m.key, label=m.label,
                    lef=tuple(v * mods[m.key].frequency for v in m.lef),
                    magnitude=(m.magnitude[0] * mods[m.key].magnitude,
                               m.magnitude[1] * mods[m.key].magnitude),
                )
                for m in marginals
            ]
        trail = trail + derived_trail

    corr, repaired = pack.matrix(correlation_overrides)
    return pack, marginals, corr, repaired, trail, revenue, facts, estimation


def run_assessment(
    industry: str,
    answers: dict | None = None,
    correlation_overrides: dict | None = None,
    alpha: float = 1.0,
    n_sims: int = N_SIMS,
    seed: int = DEFAULT_SEED,
    include_sensitivity: bool = False,
    interpret: bool = False,
    include_decisions: bool = True,
    decision_costs: dict | None = None,
    book: Book | None = None,
) -> dict:
    """Composite risk for one industry, plus the sensitivity tornado.

    `book` is a connected customer's history. Without one this is v2 exactly.
    """
    pack, marginals, corr, repaired, trail, revenue, facts, estimation = _prepare(
        industry, answers, correlation_overrides, alpha, book
    )
    out = composite_risk_correlation(
        marginals, corr, pack.id, n_sims=n_sims, seed=seed, matrix_repaired=repaired,
        extra_assumptions={
            "industry_name": pack.name,
            "annual_revenue": revenue,
            "reference_revenue": pack.reference_revenue,
            "revenue_scaling_exponent": alpha,
            "intake_adjustments": trail,
        },
    )
    out["industry_name"] = pack.name
    out["vocabulary"] = pack.vocabulary
    out["expected_annual_loss_pct_revenue"] = (
        round(out["expected_annual_loss"] / revenue, 5) if revenue else None
    )
    out["intake_adjustments"] = trail
    out["derived_facts"] = facts
    # Provenance is surfaced, never buried: how much of this is their data.
    out["estimation"] = estimation.public() if book is not None else None
    if include_sensitivity:
        out["sensitivity"] = sensitivity(marginals, corr, seed=seed)
    # The priced decisions. This is what an operator can actually act on, so it
    # is computed on the main request rather than deferred.
    scale = (revenue / pack.reference_revenue) ** alpha if revenue else 1.0
    out["decisions"] = (
        rank_decisions(
            marginals, corr,
            _apply_costs(_personalise(pack.decisions, facts), decision_costs, scale),
            revenue_scale=scale, seed=seed,
        )
        if pack.decisions and include_decisions else []
    )
    out["decision_costs"] = decision_costs or {}
    if interpret:
        out["interpretation"] = portfolio_interpretation(out)
        out["recommendations"] = build_recommendations(out)
    return out


def run_robustness(
    industry: str,
    answers: dict | None = None,
    correlation_overrides: dict | None = None,
    alpha: float = 1.0,
    eps: float = DEFAULT_EPS,
    seed: int = DEFAULT_SEED,
    book: Book | None = None,
) -> dict:
    """The dependence-uncertainty layer. Slow by design; call it separately."""
    pack, marginals, corr, _repaired, _trail, _rev, _facts, _est = _prepare(
        industry, answers, correlation_overrides, alpha, book
    )
    out = robustness_assessment(marginals, corr, eps=eps, seed=seed)
    out["industry"] = pack.id
    out["industry_name"] = pack.name
    return out
