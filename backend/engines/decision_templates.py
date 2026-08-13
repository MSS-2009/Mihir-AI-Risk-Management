"""Four decision shapes, each a validated model with stated assumptions.

Deliberately four, and deliberately not a free-form "ask about any decision"
box. A box that answers anything abandons the validated-model discipline that is
the entire differentiator: the moment the language model is choosing the maths,
nothing on screen is defensible. Each template here is a named model with a
documented payoff structure, exactly like an engine.

Every template returns two things, and the second is the one no spreadsheet can
produce: the net present value distribution, AND the effect on the risk profile,
computed by running the composite twice under common random numbers.

That second half already exists in `evaluate_decision`, which pairs a baseline
and an intervened run scenario by scenario. Templates therefore never
reimplement the simulation, they only describe the choice. Reimplementing it is
how double-counting gets in.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .constants import DEFAULT_SEED, N_SIMS
from .copula import draw_copula_inputs, uniforms_for
from .decisions import (
    DEFAULT_DISCOUNT_RATE,
    DEFAULT_HORIZON_YEARS,
    Decision,
    Intervention,
    _frequencies_from_uniforms,
    evaluate_decision,
    pert_uniforms,
)
from .fair import Marginal, portfolio_losses


@dataclass(frozen=True)
class Option:
    """One alternative inside a decision. A decision with one option is a bet."""

    id: str
    label: str
    cost_upfront: float = 0.0
    cost_annual: float = 0.0
    interventions: list[Intervention] = field(default_factory=list)
    rationale: str = ""


@dataclass(frozen=True)
class DecisionTemplate:
    """A named decision shape. `kind` selects the payoff structure."""

    id: str
    kind: str                       # one of TEMPLATE_KINDS
    title: str
    question: str
    options: list[Option]
    horizon_years: int = DEFAULT_HORIZON_YEARS
    discount_rate: float = DEFAULT_DISCOUNT_RATE
    assumptions: str = ""


TEMPLATE_KINDS = (
    "invest_or_not",
    "choose_between_options",
    "act_now_or_wait",
    "accept_or_decline_exposure",
)

KIND_DESCRIPTIONS = {
    "invest_or_not": (
        "Spend a known amount now for an uncertain future benefit. Returns the net "
        "present value distribution, the probability of a positive return, and the "
        "assumption that would flip the conclusion."
    ),
    "choose_between_options": (
        "Two or more alternatives, each with its own cost and uncertain payoff. "
        "Returns the probability each option is best and the expected regret of "
        "choosing wrongly."
    ),
    "act_now_or_wait": (
        "Pay a known cost now, or accept the risk of a larger cost later. Returns "
        "both paths priced against the same scenarios."
    ),
    "accept_or_decline_exposure": (
        "Take on a new customer, order or contract with an uncertain payoff and a "
        "concentration consequence. Returns the payoff and what it does to the tail."
    ),
}


def _shared_draws(marginals: list[Marginal], corr: np.ndarray, n_sims: int, seed: int):
    """One baseline and one set of draws for every option in a decision.

    Common random numbers are the whole reason a comparison between options
    means anything: without them the difference between two options is partly
    sampling noise, and with three options that noise compounds.
    """
    d = len(marginals)
    draws = draw_copula_inputs(d, n_sims, seed)
    freq_u = pert_uniforms(n_sims, d, seed + 1)
    u = uniforms_for(draws, corr)
    base_freqs = _frequencies_from_uniforms(marginals, freq_u)
    base_total, _ = portfolio_losses(marginals, base_freqs, u)
    return draws, freq_u, u, base_freqs, base_total


def _price_option(
    marginals, corr, option: Option, template: DecisionTemplate,
    revenue_scale: float, shared, n_sims: int, seed: int,
) -> dict:
    """Price one option using the existing evaluator, unchanged."""
    draws, freq_u, u, base_freqs, base_total = shared
    decision = Decision(
        id=option.id,
        title=option.label,
        question=template.question,
        rationale=option.rationale,
        interventions=option.interventions,
        cost_upfront=option.cost_upfront,
        cost_annual=option.cost_annual,
    )
    out = evaluate_decision(
        marginals, corr, decision,
        revenue_scale=revenue_scale,
        horizon_years=template.horizon_years,
        discount_rate=template.discount_rate,
        n_sims=n_sims, seed=seed,
        _draws=draws, _freq_u=freq_u, _u=u,
        _base_freqs=base_freqs, _base_total=base_total,
    )
    out["option_id"] = option.id
    out["label"] = option.label
    return out


def _npv_per_scenario(priced: dict, marginals, corr, option, template,
                      revenue_scale, shared, n_sims, seed) -> np.ndarray:
    """Rebuild the per-scenario NPV from the saving quantiles is NOT possible
    exactly, so recompute the paired run for the options comparison.

    Only `choose_between_options` needs per-scenario vectors, because "which
    option wins" is a scenario-by-scenario question. The single-option templates
    read everything they need off the summary.
    """
    draws, freq_u, u, base_freqs, base_total = shared
    from .decisions import apply_interventions

    decision = Decision(
        id=option.id, title=option.label, question="", rationale="",
        interventions=option.interventions,
        cost_upfront=option.cost_upfront, cost_annual=option.cost_annual,
    )
    after = apply_interventions(marginals, decision)
    touched = {iv.engine for iv in option.interventions if iv.frequency != 1.0}
    if touched:
        after_freqs = base_freqs.copy()
        for i, m in enumerate(after):
            if m.key in touched:
                after_freqs[:, i] = _frequencies_from_uniforms([m], freq_u[:, [i]])[:, 0]
    else:
        after_freqs = base_freqs
    after_total, _ = portfolio_losses(after, after_freqs, u)

    saving = base_total - after_total
    years = np.arange(1, template.horizon_years + 1)
    annuity = float(np.sum(1.0 / (1.0 + template.discount_rate) ** years))
    cost_up = option.cost_upfront * revenue_scale
    cost_yr = option.cost_annual * revenue_scale
    return -cost_up + (saving - cost_yr) * annuity


def evaluate_template(
    template: DecisionTemplate,
    marginals: list[Marginal],
    corr: np.ndarray,
    revenue_scale: float = 1.0,
    n_sims: int = N_SIMS,
    seed: int = DEFAULT_SEED,
) -> dict:
    """Price a decision template against the current risk profile.

    Returns the payoff for each option plus the risk-profile delta, which is the
    part a spreadsheet cannot produce: not only "this returns $140,000" but
    "and it reduces your portfolio P95 by $312,000".
    """
    if template.kind not in TEMPLATE_KINDS:
        raise ValueError(f"unknown template kind '{template.kind}'")
    if not template.options:
        raise ValueError("a decision needs at least one option")

    shared = _shared_draws(marginals, corr, n_sims, seed)
    priced = [
        _price_option(marginals, corr, o, template, revenue_scale, shared, n_sims, seed)
        for o in template.options
    ]

    out = {
        "id": template.id,
        "kind": template.kind,
        "kind_description": KIND_DESCRIPTIONS[template.kind],
        "title": template.title,
        "question": template.question,
        "options": priced,
        "horizon_years": template.horizon_years,
        "discount_rate": template.discount_rate,
        "assumptions": template.assumptions,
        "basis": (
            "Each option is re-run through the same scenarios with it in place, paired "
            "against the same years without it. The risk-profile effect is the "
            "difference between those two runs, not a second model."
        ),
    }

    if template.kind == "choose_between_options" and len(template.options) > 1:
        out.update(_compare(template, marginals, corr, revenue_scale, shared, n_sims, seed))
    else:
        best = max(priced, key=lambda p: p["npv"])
        out["recommended"] = best["option_id"] if best["npv"] > 0 else None
        out["verdict"] = (
            "worth doing" if best["npv"] > 0 and best["prob_beneficial"] >= 0.5
            else "marginal" if best["npv"] > 0
            else "not worth doing at these estimates"
        )
        # What would have to be true to change the answer. The number a buyer
        # argues with, rather than a verdict they can only accept or reject.
        annuity = sum(1.0 / (1.0 + template.discount_rate) ** y
                      for y in range(1, template.horizon_years + 1))
        out["break_even_annual_cost"] = round(
            best["expected_saving_annual"] - best["cost_upfront"] / annuity, 2
        )
    return out


def _compare(template, marginals, corr, revenue_scale, shared, n_sims, seed) -> dict:
    """Which option wins, and what choosing wrongly costs.

    Scenario by scenario under common random numbers, so "option A beats option
    B in 68% of scenarios" is a statement about the world rather than about two
    independent simulations that happened to differ.
    """
    npvs = np.column_stack([
        _npv_per_scenario(None, marginals, corr, o, template, revenue_scale,
                          shared, n_sims, seed)
        for o in template.options
    ])
    winner = np.argmax(npvs, axis=1)
    best_possible = npvs.max(axis=1)

    rows = []
    for i, option in enumerate(template.options):
        p_best = float((winner == i).mean())
        regret = best_possible - npvs[:, i]
        rows.append({
            "option_id": option.id,
            "label": option.label,
            "prob_best": round(p_best, 4),
            # What it costs on average to pick this one when another was better.
            "expected_regret": round(float(regret.mean()), 2),
            "regret_p90": round(float(np.percentile(regret, 90)), 2),
        })

    top = max(rows, key=lambda r: r["prob_best"])
    return {
        "comparison": rows,
        "recommended": top["option_id"],
        "verdict": (
            f"{top['label']} is best in {top['prob_best']:.0%} of scenarios"
        ),
        "decisiveness": round(
            top["prob_best"] - sorted(r["prob_best"] for r in rows)[-2], 4
        ) if len(rows) > 1 else 1.0,
    }
