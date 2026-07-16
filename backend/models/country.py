"""Country / geopolitical sourcing risk."""
import numpy as np

from ._util import pctile, risk_summary
from .registry import ModelSpec, ParamSpec, register

_DEFAULT_EXPOSURES = [
    {"country": "China", "annual_spend": 3_800_000, "disruption_prob": 0.20, "severity": 0.40},
    {"country": "Germany", "annual_spend": 1_600_000, "disruption_prob": 0.06, "severity": 0.25},
    {"country": "Mexico", "annual_spend": 900_000, "disruption_prob": 0.10, "severity": 0.30},
    {"country": "Japan", "annual_spend": 700_000, "disruption_prob": 0.05, "severity": 0.22},
]


def country_risk(
    exposures=None,
    severity_volatility=0.45,
    high_risk_threshold=0.15,
    n_sims=20000,
    seed=42,
):
    """What geopolitical concentration are you carrying, and what could it cost?

    Each sourcing country carries an annual disruption probability and a
    severity (fraction of that country's spend exposed to added cost/delay when
    disrupted, political, logistics, or sanctions-adjacent events). Monte Carlo
    draws independent country disruptions with lognormal severity and aggregates
    the annual loss. Signal layers (sanctions, key news) feed by raising a
    country's disruption probability; this model never fabricates a score.
    """
    exposures = exposures if exposures else _DEFAULT_EXPOSURES
    rng = np.random.default_rng(seed)

    spend = np.array([float(e["annual_spend"]) for e in exposures])
    total = spend.sum()
    shares = spend / total
    probs = np.array([float(e.get("disruption_prob", 0.1)) for e in exposures])
    sevs = np.array([float(e.get("severity", 0.3)) for e in exposures])

    n = len(exposures)
    events = rng.random((n_sims, n)) < probs
    sigma = np.sqrt(np.log(1 + severity_volatility ** 2))
    mult = rng.lognormal(mean=-0.5 * sigma ** 2, sigma=sigma, size=(n_sims, n))
    per_country = events * spend * sevs * mult
    losses = per_country.sum(axis=1)

    # Expected loss per country (deterministic ranking) to name the worst.
    exp_by_country = probs * spend * sevs
    worst = int(np.argmax(exp_by_country))
    high_risk_mask = probs >= high_risk_threshold

    return {
        "model": "country_risk",
        "hhi": round(float((shares ** 2).sum()), 4),
        "top_country": exposures[int(np.argmax(spend))]["country"],
        "top_country_share": round(float(shares.max()), 4),
        "worst_expected_country": exposures[worst]["country"],
        "high_risk_spend_share": round(float(shares[high_risk_mask].sum()), 4),
        "expected_annual_loss": round(float(losses.mean()), 2),
        "loss_p90": pctile(losses, 90),
        "loss_p95": pctile(losses, 95),
        "risk_summary": risk_summary(losses, "Country disruption"),
        "assumptions": {
            "n_countries": n,
            "total_spend": round(float(total), 2),
            "severity_volatility": severity_volatility,
            "high_risk_threshold": high_risk_threshold,
            "n_sims": n_sims,
        },
    }


register(
    ModelSpec(
        key="country",
        name="Country risk",
        version="1.0.0",
        domain="Geopolitical",
        method=(
            "Monte Carlo over per-country Bernoulli disruptions with lognormal "
            "severity on spend exposure; reports geographic concentration, "
            "high-risk spend share, and the annual disruption-loss distribution."
        ),
        fn=country_risk,
        params=[
            ParamSpec(
                "exposures", "Country exposures", "entity_list", _DEFAULT_EXPOSURES,
                fields=[
                    {"name": "country", "label": "Country", "type": "text"},
                    {"name": "annual_spend", "label": "Annual spend", "type": "currency"},
                    {"name": "disruption_prob", "label": "Disruption prob.", "type": "percent"},
                    {"name": "severity", "label": "Severity", "type": "percent"},
                ],
            ),
            ParamSpec("severity_volatility", "Severity volatility", "percent", 0.45, advanced=True),
            ParamSpec("high_risk_threshold", "High-risk threshold", "percent", 0.15, advanced=True),
            ParamSpec("n_sims", "Scenarios", "int", 20000, advanced=True),
        ],
        outputs=[
            {"key": "expected_annual_loss", "label": "Expected annual loss", "type": "currency"},
            {"key": "loss_p95", "label": "Tail loss (P95)", "type": "currency"},
            {"key": "high_risk_spend_share", "label": "High-risk spend share", "type": "percent"},
            {"key": "top_country_share", "label": "Top-country concentration", "type": "percent"},
        ],
    )
)
