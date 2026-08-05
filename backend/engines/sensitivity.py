"""Sensitivity analysis: which assumption actually moves the answer.

Every parameter in this product is judgment. Showing which of those judgments
the answer depends on converts that weakness into the most credible thing on the
page, and it answers "you made these up" before anyone has to ask it.

Perturb each parameter by +/-25%, re-run, record the change in portfolio P95,
sort by absolute impact. Draws are held fixed across perturbations for the same
reason they are in the robustness sweep: otherwise this measures sampling noise.
"""
from __future__ import annotations

from .constants import DEFAULT_SEED, N_SIMS_SWEEP
from .composite import run_portfolio
from .copula import draw_copula_inputs
from .fair import Marginal, frequency_draws

DELTA = 0.25


# Which parameters to perturb, and why these three.
#
# Scaling the whole frequency triple and scaling the whole magnitude pair are
# ALGEBRAICALLY THE SAME LEVER: annual loss is frequency x magnitude, so a 25%
# move in either produces an identical result. Reporting both would imply
# information that is not there. Instead we perturb three parameters that have
# genuinely distinct effects:
#
#   lef_mode        how often it typically happens (changes the PERT shape)
#   magnitude_mode  what it typically costs (also reshapes the tail, since the
#                   P90-to-mode ratio moves)
#   magnitude_p90   how bad the bad case is (pure tail shape, via sigma)
PARAMETERS = (
    ("lef_mode", "how often it typically happens"),
    ("magnitude_mode", "what it typically costs"),
    ("magnitude_p90", "how bad the bad case is"),
)


def _perturb(marginals: list[Marginal], i: int, param: str, factor: float) -> list[Marginal]:
    m = marginals[i]
    lo, mode, hi = m.lef
    mag_mode, mag_p90 = m.magnitude
    if param == "lef_mode":
        # Keep the mode inside its own bounds.
        mode = min(max(mode * factor, lo), hi)
    elif param == "magnitude_mode":
        mag_mode = mag_mode * factor
        # A lognormal's P90 must stay above its mode.
        mag_p90 = max(mag_p90, mag_mode * 1.05)
    elif param == "magnitude_p90":
        mag_p90 = max(mag_p90 * factor, mag_mode * 1.05)
    out = list(marginals)
    out[i] = Marginal(key=m.key, label=m.label, lef=(lo, mode, hi), magnitude=(mag_mode, mag_p90))
    return out


def sensitivity(
    marginals: list[Marginal],
    corr,
    delta: float = DELTA,
    n_sims: int = N_SIMS_SWEEP,
    seed: int = DEFAULT_SEED,
) -> list[dict]:
    """Tornado rows, sorted by absolute impact on portfolio P95."""
    draws = draw_copula_inputs(len(marginals), n_sims, seed)

    def p95_for(ms: list[Marginal]) -> float:
        # Frequency draws depend on the PERT parameters, so they are rebuilt
        # per variant. The copula draws stay fixed, which is what isolates the
        # parameter change from sampling noise in the dependence structure.
        return run_portfolio(ms, corr, draws, frequency_draws(ms, n_sims, seed + 1)).pct(95)

    base = p95_for(marginals)
    rows = []
    for i, m in enumerate(marginals):
        for param, phrase in PARAMETERS:
            hi = p95_for(_perturb(marginals, i, param, 1 + delta))
            lo = p95_for(_perturb(marginals, i, param, 1 - delta))
            rows.append(
                {
                    "engine": m.key,
                    "label": m.label,
                    "parameter": param,
                    "parameter_label": f"{m.label}: {phrase}",
                    "low_p95": round(lo, 2),
                    "high_p95": round(hi, 2),
                    "low_delta": round(lo - base, 2),
                    "high_delta": round(hi - base, 2),
                    "impact": round(abs(hi - lo), 2),
                    "impact_pct": round(abs(hi - lo) / base, 4) if base else 0.0,
                }
            )
    rows.sort(key=lambda r: -r["impact"])
    return [{"base_p95": round(base, 2), "delta": delta, **r} for r in rows]
