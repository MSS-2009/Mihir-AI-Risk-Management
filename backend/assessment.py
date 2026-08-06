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

from engines.composite import composite_risk_correlation
from engines.decisions import rank_decisions
from engines.constants import DEFAULT_SEED, N_SIMS
from engines.modulation import apply_modulations
from engines.robustness import DEFAULT_EPS, robustness_assessment
from agents.portfolio import build_recommendations, portfolio_interpretation
from engines.sensitivity import sensitivity
from industries import get_pack

REVENUE_QUESTION = "annual_revenue"


def _prepare(industry: str, answers: dict | None, correlation_overrides: dict | None, alpha: float):
    """Resolve a pack plus intake answers into marginals and a matrix."""
    pack = get_pack(industry)
    answers = answers or {}
    revenue = answers.get(REVENUE_QUESTION) or pack.reference_revenue
    marginals = pack.marginals(revenue=revenue, alpha=alpha)
    marginals, trail = apply_modulations(marginals, answers, pack.questions)
    corr, repaired = pack.matrix(correlation_overrides)
    return pack, marginals, corr, repaired, trail, revenue


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
) -> dict:
    """Composite risk for one industry, plus the sensitivity tornado."""
    pack, marginals, corr, repaired, trail, revenue = _prepare(
        industry, answers, correlation_overrides, alpha
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
    if include_sensitivity:
        out["sensitivity"] = sensitivity(marginals, corr, seed=seed)
    # The priced decisions. This is what an operator can actually act on, so it
    # is computed on the main request rather than deferred.
    scale = (revenue / pack.reference_revenue) ** alpha if revenue else 1.0
    out["decisions"] = (
        rank_decisions(marginals, corr, pack.decisions, revenue_scale=scale, seed=seed)
        if pack.decisions and include_decisions else []
    )
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
) -> dict:
    """The dependence-uncertainty layer. Slow by design; call it separately."""
    pack, marginals, corr, _repaired, _trail, _rev = _prepare(
        industry, answers, correlation_overrides, alpha
    )
    out = robustness_assessment(marginals, corr, eps=eps, seed=seed)
    out["industry"] = pack.id
    out["industry_name"] = pack.name
    return out
