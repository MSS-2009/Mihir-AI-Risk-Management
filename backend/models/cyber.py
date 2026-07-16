"""Cybersecurity loss exposure (FAIR-style)."""
import numpy as np

from ._util import clamp01, pctile, risk_summary
from .registry import ModelSpec, ParamSpec, register


def cyber_loss_exposure(
    records_held=20_000,
    annual_revenue=120_000_000,
    control_maturity=3,
    industry_base_frequency=0.28,
    cost_per_record=95.0,
    secondary_loss_revenue_pct=0.008,
    magnitude_volatility=0.6,
    n_sims=50000,
    seed=42,
):
    """Annual cyber loss exposure, FAIR-style.

    Loss Event Frequency is the industry base breach frequency scaled by control
    maturity (1-5). Each event's magnitude is a lognormal draw combining primary
    loss (records x direct cost-per-record) and a firm-specific secondary loss (a
    fraction of revenue for business interruption). Cost-per-record is the
    *direct* figure, so this does not double-count the lost-business component the
    way an all-in per-record benchmark would. Annual loss sums a Poisson number of
    events. Reports expected annual loss and the P95 tail, the number a breach
    actually costs, not just the average.
    """
    rng = np.random.default_rng(seed)

    maturity_factor = float(np.clip(1.6 - 0.25 * (control_maturity - 1), 0.3, 1.6))
    lef = industry_base_frequency * maturity_factor  # loss event frequency (per yr)

    primary = records_held * cost_per_record
    secondary = annual_revenue * secondary_loss_revenue_pct
    mean_magnitude = primary + secondary
    sigma = np.sqrt(np.log(1 + magnitude_volatility ** 2))
    mu = np.log(max(mean_magnitude, 1.0)) - 0.5 * sigma ** 2

    n_events = rng.poisson(lef, n_sims)
    total_events = int(n_events.sum())
    mags = rng.lognormal(mean=mu, sigma=sigma, size=total_events)
    losses = np.zeros(n_sims)
    if total_events:
        idx = np.repeat(np.arange(n_sims), n_events)
        np.add.at(losses, idx, mags)

    return {
        "model": "cyber_loss_fair",
        "loss_event_frequency": round(lef, 3),
        "prob_breach_this_year": round(float(1 - np.exp(-lef)), 3),
        "expected_single_event_loss": round(float(mean_magnitude), 2),
        "single_event_p95": round(float(np.exp(mu + 1.645 * sigma)), 2),
        "expected_annual_loss": round(float(losses.mean()), 2),
        "loss_p90": pctile(losses, 90),
        "loss_p95": pctile(losses, 95),
        "loss_p99": pctile(losses, 99),
        "control_maturity": control_maturity,
        "risk_summary": risk_summary(losses, "Cyber breach"),
        "assumptions": {
            "records_held": records_held,
            "annual_revenue": annual_revenue,
            "control_maturity": control_maturity,
            "industry_base_frequency": industry_base_frequency,
            "cost_per_record": cost_per_record,
            "secondary_loss_revenue_pct": secondary_loss_revenue_pct,
            "magnitude_volatility": magnitude_volatility,
            "n_sims": n_sims,
        },
    }


register(
    ModelSpec(
        key="cyber",
        name="Cyber loss exposure",
        version="1.0.0",
        domain="Cybersecurity",
        method=(
            "FAIR: loss-event frequency (industry base scaled by control "
            "maturity) times a lognormal loss magnitude (records x cost plus a "
            "revenue-linked secondary loss), summed over a Poisson event count."
        ),
        fn=cyber_loss_exposure,
        params=[
            ParamSpec("records_held", "Sensitive records held", "int", 20_000),
            ParamSpec("annual_revenue", "Annual revenue", "currency", 120_000_000, unit="USD"),
            ParamSpec("control_maturity", "Control maturity (1-5)", "int", 3, min=1, max=5),
            ParamSpec("industry_base_frequency", "Industry breach frequency", "percent", 0.28, advanced=True),
            ParamSpec("cost_per_record", "Direct cost per record", "currency", 95.0, advanced=True),
            ParamSpec("secondary_loss_revenue_pct", "Business-interruption loss (% revenue)", "percent", 0.008, advanced=True),
            ParamSpec("magnitude_volatility", "Magnitude volatility", "percent", 0.6, advanced=True),
            ParamSpec("n_sims", "Scenarios", "int", 50000, advanced=True),
        ],
        outputs=[
            {"key": "expected_annual_loss", "label": "Expected annual loss", "type": "currency"},
            {"key": "loss_p95", "label": "Tail loss (P95)", "type": "currency"},
            {"key": "prob_breach_this_year", "label": "Probability of breach", "type": "percent"},
            {"key": "single_event_p95", "label": "Severe single event (P95)", "type": "currency"},
        ],
    )
)
