"""Priced decisions: what should we actually do, and is it worth it.

This is the difference between a diagnostic and a product. "Your P99 is $5.8M"
is a fact. "Dual-sourcing the Jiangsu line costs $340K, saves $210K a year, and
is worth doing in 71% of scenarios" is something an operator can approve or
reject on Monday.

A decision is an INTERVENTION: it changes the parameters of one or more engines,
at a cost. We re-run the portfolio with those parameters and compare.

COMMON RANDOM NUMBERS
---------------------
The comparison is only meaningful if the baseline and the intervened run share
their randomness, otherwise the "saving" is partly sampling noise. Both runs use
the same copula draws AND the same frequency uniforms, so every scenario is the
same world with and without the intervention. That is what makes a per-scenario
saving, and therefore a probability of the decision being worth it, well defined.

Note this evaluator draws frequency by inverse CDF rather than by direct beta
sampling, because an intervention changes the PERT parameters and only the
inverse-CDF route keeps the two runs paired scenario for scenario. The headline
assessment still uses the pinned sampling path, so the two agree to within Monte
Carlo noise rather than exactly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.stats import beta as beta_dist

from .constants import DEFAULT_SEED, N_SIMS
from .copula import CopulaDraws, draw_copula_inputs, uniforms_for
from .fair import Marginal, pert_params, portfolio_losses

DEFAULT_HORIZON_YEARS = 3
DEFAULT_DISCOUNT_RATE = 0.10


@dataclass(frozen=True)
class Intervention:
    """What a decision does to one engine's parameters.

    Multipliers below 1.0 reduce exposure. Frequency and magnitude are separate
    because real levers act differently: a second source mostly changes how
    badly a failure hurts, while better controls mostly change how often one
    turns into a loss.
    """

    engine: str
    frequency: float = 1.0
    magnitude: float = 1.0


@dataclass(frozen=True)
class Decision:
    """One choice an operator can actually make, with what it costs.

    Costs are starting estimates at the pack's reference revenue, scaled to the
    user's revenue and editable, exactly like every other parameter here.
    """

    id: str
    title: str                       # the action, in the operator's words
    question: str                    # the decision as they would phrase it
    rationale: str                   # why this lever moves this exposure
    interventions: list[Intervention]
    cost_upfront: float = 0.0        # one-time, at reference revenue
    cost_annual: float = 0.0         # recurring, at reference revenue
    effort: str = "moderate"         # low | moderate | high
    reversible: bool = True


def pert_uniforms(n_sims: int, d: int, seed: int) -> np.ndarray:
    """Shared uniforms for frequency, held fixed across baseline and intervention."""
    return np.random.default_rng(seed).random((n_sims, d))


def _frequencies_from_uniforms(marginals: list[Marginal], u: np.ndarray) -> np.ndarray:
    """PERT frequencies by inverse CDF, so the two runs stay paired."""
    cols = []
    for i, m in enumerate(marginals):
        a, b, span = pert_params(*m.lef)
        cols.append(m.lef[0] + beta_dist.ppf(np.clip(u[:, i], 1e-9, 1 - 1e-9), a, b) * span)
    return np.column_stack(cols)


def apply_interventions(marginals: list[Marginal], decision: Decision) -> list[Marginal]:
    by_engine = {iv.engine: iv for iv in decision.interventions}
    out = []
    for m in marginals:
        iv = by_engine.get(m.key)
        if not iv or (iv.frequency == 1.0 and iv.magnitude == 1.0):
            out.append(m)
            continue
        out.append(
            Marginal(
                key=m.key,
                label=m.label,
                lef=tuple(v * iv.frequency for v in m.lef),
                magnitude=(m.magnitude[0] * iv.magnitude, m.magnitude[1] * iv.magnitude),
            )
        )
    return out


def evaluate_decision(
    marginals: list[Marginal],
    corr: np.ndarray,
    decision: Decision,
    revenue_scale: float = 1.0,
    horizon_years: int = DEFAULT_HORIZON_YEARS,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
    n_sims: int = N_SIMS,
    seed: int = DEFAULT_SEED,
    _draws: CopulaDraws | None = None,
    _freq_u: np.ndarray | None = None,
    _u: np.ndarray | None = None,
    _base_freqs: np.ndarray | None = None,
    _base_total: np.ndarray | None = None,
) -> dict:
    """Price one decision against the portfolio it changes.

    The baseline is identical for every decision, so callers that price several
    at once pass it in rather than paying for it repeatedly.
    """
    d = len(marginals)
    draws = _draws if _draws is not None else draw_copula_inputs(d, n_sims, seed)
    freq_u = _freq_u if _freq_u is not None else pert_uniforms(n_sims, d, seed + 1)
    u = _u if _u is not None else uniforms_for(draws, corr)

    base_freqs = _base_freqs if _base_freqs is not None else _frequencies_from_uniforms(marginals, freq_u)
    if _base_total is not None:
        base_total = _base_total
    else:
        base_total, _ = portfolio_losses(marginals, base_freqs, u)

    after = apply_interventions(marginals, decision)
    # Only columns whose frequency actually moved need re-drawing; the inverse
    # CDF is the expensive step here.
    touched = {iv.engine for iv in decision.interventions if iv.frequency != 1.0}
    if touched:
        after_freqs = base_freqs.copy()
        for i, m in enumerate(after):
            if m.key in touched:
                after_freqs[:, i] = _frequencies_from_uniforms([m], freq_u[:, [i]])[:, 0]
    else:
        after_freqs = base_freqs
    after_total, _ = portfolio_losses(after, after_freqs, u)

    # Paired, scenario by scenario: the same year with and without the action.
    saving = base_total - after_total
    cost_up = decision.cost_upfront * revenue_scale
    cost_yr = decision.cost_annual * revenue_scale

    # Present value of an annuity over the horizon.
    years = np.arange(1, horizon_years + 1)
    annuity = float(np.sum(1.0 / (1.0 + discount_rate) ** years))
    npv_per_scenario = -cost_up + (saving - cost_yr) * annuity

    expected_saving = float(saving.mean())
    net_annual = expected_saving - cost_yr
    payback = (cost_up / net_annual) if net_annual > 0 and cost_up > 0 else None

    # The saving distribution, so the cost can be edited without re-simulating.
    #
    # NPV is affine in cost: npv_s = -upfront + (saving_s - annual) * annuity.
    # That makes every headline figure recomputable from the saving quantiles
    # alone, exactly for the mean and the percentiles, and to a quarter of a
    # percent for the probability. A cost field the operator can drag is worth
    # far more than one that is right to four decimal places, and a 0.5-second
    # round trip per keystroke would have made it unusable.
    grid = np.linspace(0.0, 100.0, 201)
    saving_quantiles = [round(float(x), 2) for x in np.percentile(saving, grid)]

    return {
        "id": decision.id,
        "title": decision.title,
        "question": decision.question,
        "rationale": decision.rationale,
        "engines": [iv.engine for iv in decision.interventions],
        "effort": decision.effort,
        "reversible": decision.reversible,
        "cost_upfront": round(cost_up, 2),
        "cost_annual": round(cost_yr, 2),
        "expected_saving_annual": round(expected_saving, 2),
        "saving_p10": round(float(np.percentile(saving, 10)), 2),
        "saving_p90": round(float(np.percentile(saving, 90)), 2),
        "net_annual": round(net_annual, 2),
        "npv": round(float(npv_per_scenario.mean()), 2),
        "npv_p10": round(float(np.percentile(npv_per_scenario, 10)), 2),
        "npv_p90": round(float(np.percentile(npv_per_scenario, 90)), 2),
        "prob_beneficial": round(float((npv_per_scenario > 0).mean()), 4),
        "payback_years": round(payback, 2) if payback and payback < 100 else None,
        "p95_reduction": round(
            float(np.percentile(base_total, 95) - np.percentile(after_total, 95)), 2
        ),
        "p99_reduction": round(
            float(np.percentile(base_total, 99) - np.percentile(after_total, 99)), 2
        ),
        "baseline_expected_loss": round(float(base_total.mean()), 2),
        "horizon_years": horizon_years,
        "discount_rate": discount_rate,
        "annuity_factor": round(annuity, 6),
        "saving_quantiles": saving_quantiles,
        "cost_editable": True,
        "basis": (
            "Cost is a starting estimate you can edit. Saving is computed by re-running "
            "the same 50,000 scenarios with this action in place, paired scenario by "
            "scenario against the same years without it."
        ),
    }


def rank_decisions(
    marginals: list[Marginal],
    corr: np.ndarray,
    decisions: list[Decision],
    revenue_scale: float = 1.0,
    n_sims: int = N_SIMS,
    seed: int = DEFAULT_SEED,
    **kw,
) -> list[dict]:
    """Every decision, priced and ranked by expected net present value.

    The draws are built once and shared, so decisions are comparable with each
    other as well as against the baseline.
    """
    d = len(marginals)
    draws = draw_copula_inputs(d, n_sims, seed)
    freq_u = pert_uniforms(n_sims, d, seed + 1)
    u = uniforms_for(draws, corr)
    base_freqs = _frequencies_from_uniforms(marginals, freq_u)
    base_total, _ = portfolio_losses(marginals, base_freqs, u)
    out = [
        evaluate_decision(
            marginals, corr, dec, revenue_scale=revenue_scale,
            n_sims=n_sims, seed=seed, _draws=draws, _freq_u=freq_u,
            _u=u, _base_freqs=base_freqs, _base_total=base_total, **kw,
        )
        for dec in decisions
    ]
    out.sort(key=lambda r: -r["npv"])
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out
