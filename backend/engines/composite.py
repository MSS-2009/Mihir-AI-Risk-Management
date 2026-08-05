"""Composite portfolio risk: correlated aggregate versus independent baseline.

The headline comparison is a correlated portfolio against an independent
portfolio with IDENTICAL marginals. It is deliberately not "the sum of each
domain's standalone P95", which is a different quantity, is naturally larger
than a portfolio percentile, and produces a negative gap that destroys the
claim.

Two properties are stated plainly rather than hidden:

  1. Expected loss is essentially unchanged by correlation. Expectation is
     linear. Dependence moves the tail, not the average.
  2. The strongest output is the joint-breach figure: how much more often
     several domains blow past their own 90th percentile at the same time than
     independent modelling predicts.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .constants import DEFAULT_SEED, N_SIMS
from .copula import (
    COPULA_DF,
    CopulaDraws,
    draw_copula_inputs,
    independent_uniforms,
    uniforms_for,
)
from .fair import Marginal, closed_form_expected_loss, frequency_draws, portfolio_losses

VERSION = "1.0.0"
METHOD = (
    "FAIR marginals (PERT frequency x lognormal magnitude calibrated to mode and "
    "P90), t-copula dependence (df=4) applied to magnitude"
)
EXCEEDANCE_POINTS = (50, 75, 90, 95, 99)
BREACH_PERCENTILE = 90


@dataclass(frozen=True)
class PortfolioRun:
    """One evaluation of the portfolio at a given correlation matrix."""

    total: np.ndarray        # (n_sims,) annual loss
    per_domain: np.ndarray   # (n_sims, d)

    def pct(self, p: float) -> float:
        return float(np.percentile(self.total, p))


def run_portfolio(
    marginals: list[Marginal], corr: np.ndarray, draws: CopulaDraws, freqs: np.ndarray
) -> PortfolioRun:
    """Evaluate the portfolio for one correlation matrix.

    `draws` and `freqs` are supplied by the caller and held fixed across matrix
    variations, so any difference in the result is attributable to dependence
    alone. This is what makes the robustness band meaningful.
    """
    total, per_domain = portfolio_losses(marginals, freqs, uniforms_for(draws, corr))
    return PortfolioRun(total=total, per_domain=per_domain)


def _joint_breach(per_domain: np.ndarray, thresholds: np.ndarray) -> dict:
    """Fraction of scenarios where 2+ / 3+ domains exceed their own threshold.

    Thresholds are computed once (from the correlated run) and applied to both
    runs, so the comparison asks the same question of each: how often do several
    domains exceed the SAME loss levels simultaneously.
    """
    breaches = (per_domain >= thresholds).sum(axis=1)
    return {
        "two_plus": round(float((breaches >= 2).mean()), 6),
        "three_plus": round(float((breaches >= 3).mean()), 6),
    }


def _domain_contributions(
    marginals: list[Marginal], run: PortfolioRun, tail_p: float = 95
) -> list[dict]:
    """How each domain's share of loss shifts between the body and the tail."""
    cutoff = run.pct(tail_p)
    in_tail = run.total >= cutoff
    base_total = run.per_domain.mean(axis=0).sum()
    tail_total = run.per_domain[in_tail].mean(axis=0).sum()
    out = []
    for i, m in enumerate(marginals):
        base = float(run.per_domain[:, i].mean())
        tail = float(run.per_domain[in_tail, i].mean())
        out.append(
            {
                "domain": m.key,
                "label": m.label,
                "base_share": round(base / base_total, 4) if base_total else 0.0,
                "tail_share": round(tail / tail_total, 4) if tail_total else 0.0,
                "expected_annual_loss": round(m.expected_annual_loss, 2),
            }
        )
    out.sort(key=lambda r: -r["tail_share"])
    return out


def composite_risk_correlation(
    marginals: list[Marginal],
    corr: np.ndarray,
    industry: str,
    n_sims: int = N_SIMS,
    seed: int = DEFAULT_SEED,
    matrix_repaired: bool = False,
    extra_assumptions: dict | None = None,
) -> dict:
    """Full composite assessment for one industry.

    Returns the §4.6 output contract. `assumptions` carries every input needed
    to reproduce the run exactly, including the full correlation matrix.
    """
    if len(marginals) < 2:
        raise ValueError("composite requires at least 2 domains")

    d = len(marginals)
    keys = [m.key for m in marginals]

    # Shared inputs. The independent baseline reuses the SAME frequency draws so
    # that only the dependence structure differs between the two runs.
    draws = draw_copula_inputs(d, n_sims, seed)
    freqs = frequency_draws(marginals, n_sims, seed + 1)

    correlated = run_portfolio(marginals, corr, draws, freqs)

    # Independent baseline: plain iid uniforms. It must NOT reuse the shared
    # chi-square, because that common variate is exactly what creates t-copula
    # tail dependence and would leave the baseline coupled in the tail.
    indep_total, indep_per = portfolio_losses(
        marginals, freqs, independent_uniforms(n_sims, d, seed + 2)
    )
    independent = PortfolioRun(total=indep_total, per_domain=indep_per)

    thresholds = np.percentile(correlated.per_domain, BREACH_PERCENTILE, axis=0)
    jb_corr = _joint_breach(correlated.per_domain, thresholds)
    jb_indep = _joint_breach(independent.per_domain, thresholds)

    def premium(p: float) -> float:
        base = independent.pct(p)
        return round(correlated.pct(p) / base - 1, 4) if base > 0 else 0.0

    return {
        "industry": industry,
        "model": "composite_risk_correlation",
        "version": VERSION,
        "seed": seed,
        "method": METHOD,
        "n_sims": n_sims,
        "expected_annual_loss": round(float(correlated.total.mean()), 2),
        "expected_annual_loss_closed_form": round(closed_form_expected_loss(marginals), 2),
        "expected_annual_loss_independent": round(float(independent.total.mean()), 2),
        "exceedance_curve": [
            {"percentile": p, "loss": round(correlated.pct(p), 2)} for p in EXCEEDANCE_POINTS
        ],
        "exceedance_curve_independent": [
            {"percentile": p, "loss": round(independent.pct(p), 2)} for p in EXCEEDANCE_POINTS
        ],
        "correlation_premium": {"p95": premium(95), "p99": premium(99)},
        "joint_breach": {
            "breach_percentile": BREACH_PERCENTILE,
            "two_plus": jb_corr["two_plus"],
            "three_plus": jb_corr["three_plus"],
            "two_plus_independent": jb_indep["two_plus"],
            "three_plus_independent": jb_indep["three_plus"],
        },
        "domain_contributions": _domain_contributions(marginals, correlated),
        "assumptions": {
            "domains": [m.public() for m in marginals],
            "correlation_matrix": {
                "keys": keys,
                "labels": [m.label for m in marginals],
                "matrix": [[round(float(v), 4) for v in row] for row in corr],
                "repaired": matrix_repaired,
            },
            "copula": {"family": "student_t", "df": COPULA_DF, "applied_to": "magnitude"},
            "n_sims": n_sims,
            "seed": seed,
            "parameter_basis": (
                "Starting estimates from expert judgment, not measured loss data. "
                "Adjust to your own experience."
            ),
            **(extra_assumptions or {}),
        },
    }
