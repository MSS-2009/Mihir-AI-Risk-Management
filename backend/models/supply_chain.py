"""Supply-chain risk, supplier concentration and delivery reliability."""
import numpy as np

from ._util import pctile, risk_summary
from .registry import ModelSpec, ParamSpec, register

_DEFAULT_SUPPLIERS = [
    {"name": "Jiangsu Machine Works", "country": "CN", "annual_spend": 3_800_000, "disruption_prob": 0.18},
    {"name": "Nord Hydraulik", "country": "DE", "annual_spend": 1_600_000, "disruption_prob": 0.05},
    {"name": "Monterrey Castings", "country": "MX", "annual_spend": 900_000, "disruption_prob": 0.09},
    {"name": "Osaka Bearings", "country": "JP", "annual_spend": 700_000, "disruption_prob": 0.04},
]


def supplier_concentration_risk(
    suppliers=None,
    disruption_severity=0.35,
    severity_volatility=0.4,
    n_sims=20000,
    seed=42,
):
    """How concentrated is your supplier base, and what does a disruption cost?

    Computes the Herfindahl-Hirschman Index on spend shares (a standard
    concentration measure), then Monte Carlo: each supplier independently
    disrupts (Bernoulli) with a lognormal severity multiplier on the fraction of
    spend at risk. Reports concentration, single-source exposure, and the annual
    disruption-loss distribution, the tail is kept, never trimmed.
    """
    suppliers = suppliers if suppliers else _DEFAULT_SUPPLIERS
    rng = np.random.default_rng(seed)

    spend = np.array([float(s["annual_spend"]) for s in suppliers])
    total = spend.sum()
    shares = spend / total
    hhi = float((shares ** 2).sum())
    probs = np.array([float(s.get("disruption_prob", 0.08)) for s in suppliers])

    # Per-sim, per-supplier disruption with lognormal severity (mean-preserving).
    n = len(suppliers)
    events = rng.random((n_sims, n)) < probs
    sigma = np.sqrt(np.log(1 + severity_volatility ** 2))
    sev = rng.lognormal(mean=-0.5 * sigma ** 2, sigma=sigma, size=(n_sims, n))
    per_supplier_loss = events * spend * disruption_severity * sev
    losses = per_supplier_loss.sum(axis=1)

    top_idx = int(np.argmax(spend))
    return {
        "model": "supplier_concentration",
        "hhi": round(hhi, 4),
        "effective_suppliers": round(1.0 / hhi, 2),
        "top_supplier": suppliers[top_idx]["name"],
        "top_supplier_share": round(float(shares[top_idx]), 4),
        "single_source_spend_at_risk": round(float(spend[top_idx]), 2),
        "expected_annual_loss": round(float(losses.mean()), 2),
        "loss_p90": pctile(losses, 90),
        "loss_p95": pctile(losses, 95),
        "risk_summary": risk_summary(losses, "Supplier disruption"),
        "assumptions": {
            "n_suppliers": n,
            "total_spend": round(float(total), 2),
            "disruption_severity": disruption_severity,
            "severity_volatility": severity_volatility,
            "n_sims": n_sims,
        },
    }


def delivery_reliability(
    annual_cogs_through_lane=6_000_000,
    on_time_rate=0.86,
    avg_lead_time_days=45,
    lead_time_std_days=12,
    inventory_days_cover=50,
    disruption_prob=0.12,
    disruption_extra_days=30,
    gross_margin=0.28,
    expedite_cost_per_day=4_000,
    n_sims=20000,
    seed=42,
):
    """What do late shipments cost you in stockouts and expediting?

    Draws lead times from a normal around the historical average, adds a
    lognormal shock when a disruption occurs, and compares against inventory
    days-of-cover. Days short of cover drive lost gross margin plus expediting
    cost. Reports the annual stockout-cost distribution and days-of-cover under a
    shock.
    """
    rng = np.random.default_rng(seed)
    daily_revenue = annual_cogs_through_lane / (1 - gross_margin) / 365.0

    lead = rng.normal(avg_lead_time_days, lead_time_std_days, n_sims)
    disrupt = rng.random(n_sims) < disruption_prob
    sigma = np.sqrt(np.log(1 + 0.5 ** 2))
    shock = rng.lognormal(mean=np.log(disruption_extra_days) - 0.5 * sigma ** 2, sigma=sigma, size=n_sims)
    lead = np.clip(lead + disrupt * shock, 0, None)

    days_short = np.clip(lead - inventory_days_cover, 0, None)
    lost_margin = days_short * daily_revenue * gross_margin
    expedite = disrupt * days_short * expedite_cost_per_day
    losses = lost_margin + expedite

    return {
        "model": "delivery_reliability",
        "prob_stockout": round(float((days_short > 0).mean()), 3),
        "expected_days_short": round(float(days_short.mean()), 1),
        "days_short_p90": round(float(np.percentile(days_short, 90)), 1),
        "expected_annual_stockout_cost": round(float(losses.mean()), 2),
        "cost_p90": pctile(losses, 90),
        "cost_p95": pctile(losses, 95),
        "days_of_cover_under_shock": round(float(max(0, inventory_days_cover - np.percentile(lead, 90))), 1),
        "risk_summary": risk_summary(losses, "Delivery disruption"),
        "assumptions": {
            "annual_cogs_through_lane": annual_cogs_through_lane,
            "on_time_rate": on_time_rate,
            "avg_lead_time_days": avg_lead_time_days,
            "lead_time_std_days": lead_time_std_days,
            "inventory_days_cover": inventory_days_cover,
            "disruption_prob": disruption_prob,
            "disruption_extra_days": disruption_extra_days,
            "gross_margin": gross_margin,
            "expedite_cost_per_day": expedite_cost_per_day,
            "n_sims": n_sims,
        },
    }


register(
    ModelSpec(
        key="supplier_concentration",
        name="Supplier concentration risk",
        version="1.0.0",
        domain="Supply chain",
        method=(
            "HHI on supplier spend shares plus Monte Carlo over independent "
            "Bernoulli disruptions with lognormal severity; reports concentration, "
            "single-source exposure, and the annual disruption-loss distribution."
        ),
        fn=supplier_concentration_risk,
        params=[
            ParamSpec(
                "suppliers", "Suppliers", "entity_list", _DEFAULT_SUPPLIERS,
                fields=[
                    {"name": "name", "label": "Name", "type": "text"},
                    {"name": "country", "label": "Country", "type": "text"},
                    {"name": "annual_spend", "label": "Annual spend", "type": "currency"},
                    {"name": "disruption_prob", "label": "Disruption prob.", "type": "percent"},
                ],
            ),
            ParamSpec("disruption_severity", "Disruption severity", "percent", 0.35, advanced=True),
            ParamSpec("severity_volatility", "Severity volatility", "percent", 0.4, advanced=True),
            ParamSpec("n_sims", "Scenarios", "int", 20000, advanced=True),
        ],
        outputs=[
            {"key": "hhi", "label": "Concentration (HHI)", "type": "number"},
            {"key": "single_source_spend_at_risk", "label": "Single-source spend at risk", "type": "currency"},
            {"key": "expected_annual_loss", "label": "Expected annual loss", "type": "currency"},
            {"key": "loss_p95", "label": "Tail loss (P95)", "type": "currency"},
        ],
    )
)


register(
    ModelSpec(
        key="delivery",
        name="Delivery reliability",
        version="1.0.0",
        domain="Supply chain",
        method=(
            "Monte Carlo over lead times (normal + lognormal disruption shock) "
            "versus inventory days-of-cover; days short drive lost gross margin "
            "and expediting cost into an annual stockout-cost distribution."
        ),
        fn=delivery_reliability,
        params=[
            ParamSpec("annual_cogs_through_lane", "Annual COGS through this lane", "currency", 6_000_000, unit="USD"),
            ParamSpec("on_time_rate", "Historical on-time rate", "percent", 0.86),
            ParamSpec("avg_lead_time_days", "Average lead time", "int", 45, unit="days"),
            ParamSpec("lead_time_std_days", "Lead-time variability", "int", 12, unit="days"),
            ParamSpec("inventory_days_cover", "Inventory days of cover", "int", 50, unit="days"),
            ParamSpec("disruption_prob", "Disruption probability", "percent", 0.12),
            ParamSpec("disruption_extra_days", "Added days under disruption", "int", 30, unit="days"),
            ParamSpec("gross_margin", "Gross margin", "percent", 0.28),
            ParamSpec("expedite_cost_per_day", "Expedite cost per day", "currency", 4_000, advanced=True),
            ParamSpec("n_sims", "Scenarios", "int", 20000, advanced=True),
        ],
        outputs=[
            {"key": "expected_annual_stockout_cost", "label": "Expected annual stockout cost", "type": "currency"},
            {"key": "cost_p95", "label": "Tail cost (P95)", "type": "currency"},
            {"key": "prob_stockout", "label": "Probability of stockout", "type": "percent"},
            {"key": "expected_days_short", "label": "Expected days short", "type": "number"},
        ],
    )
)
