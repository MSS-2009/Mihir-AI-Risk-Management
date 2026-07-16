"""Product price & demand volatility risk."""
import numpy as np

from ._util import pctile, risk_summary
from .registry import ModelSpec, ParamSpec, register


def price_demand_volatility(
    annual_units=12_000,
    unit_price=850.0,
    unit_cost=610.0,
    price_volatility=0.12,
    demand_volatility=0.18,
    price_demand_correlation=-0.35,
    fixed_costs=1_200_000,
    margin_floor=0.10,
    n_sims=20000,
    seed=42,
):
    """How much could price and demand swings move your gross profit?

    Draws correlated annual price and demand shocks (bivariate normal via a 2x2
    Cholesky factor, negative correlation captures price elasticity) and
    recomputes revenue, gross profit and gross margin per scenario. Reports the
    gross-profit distribution, the probability margin falls below a floor, and
    the downside loss relative to the expected outcome.
    """
    rng = np.random.default_rng(seed)

    cov = np.array([
        [price_volatility ** 2, price_demand_correlation * price_volatility * demand_volatility],
        [price_demand_correlation * price_volatility * demand_volatility, demand_volatility ** 2],
    ])
    L = np.linalg.cholesky(cov)
    z = rng.standard_normal((n_sims, 2))
    shocks = z @ L.T
    price = unit_price * (1 + shocks[:, 0])
    units = np.clip(annual_units * (1 + shocks[:, 1]), 0, None)

    revenue = units * price
    gross_profit = units * (price - unit_cost) - fixed_costs
    with np.errstate(divide="ignore", invalid="ignore"):
        margin = np.where(revenue > 0, (units * (price - unit_cost)) / revenue, 0.0)

    expected_gp = float(gross_profit.mean())
    downside = np.clip(expected_gp - gross_profit, 0, None)

    return {
        "model": "price_demand_volatility",
        "expected_gross_profit": round(expected_gp, 2),
        "gross_profit_p10": pctile(gross_profit, 10),
        "gross_profit_p90": pctile(gross_profit, 90),
        "expected_gross_margin": round(float(margin.mean()), 4),
        "prob_margin_breach": round(float((margin < margin_floor).mean()), 3),
        "prob_loss": round(float((gross_profit < 0).mean()), 3),
        "revenue_p10": pctile(revenue, 10),
        "revenue_p90": pctile(revenue, 90),
        "risk_summary": risk_summary(downside, "Price/demand downside"),
        "assumptions": {
            "annual_units": annual_units,
            "unit_price": unit_price,
            "unit_cost": unit_cost,
            "price_volatility": price_volatility,
            "demand_volatility": demand_volatility,
            "price_demand_correlation": price_demand_correlation,
            "fixed_costs": fixed_costs,
            "margin_floor": margin_floor,
            "n_sims": n_sims,
        },
    }


register(
    ModelSpec(
        key="price",
        name="Price & demand volatility",
        version="1.0.0",
        domain="Revenue",
        method=(
            "Correlated bivariate-normal price and demand shocks (2x2 Cholesky, "
            "negative correlation for elasticity) recompute gross profit and "
            "margin per scenario; reports the gross-profit range, margin-breach "
            "probability and downside relative to expectation."
        ),
        fn=price_demand_volatility,
        params=[
            ParamSpec("annual_units", "Annual units sold", "int", 12_000),
            ParamSpec("unit_price", "Unit price", "currency", 850.0, unit="USD"),
            ParamSpec("unit_cost", "Unit cost", "currency", 610.0, unit="USD"),
            ParamSpec("price_volatility", "Price volatility", "percent", 0.12),
            ParamSpec("demand_volatility", "Demand volatility", "percent", 0.18),
            ParamSpec("price_demand_correlation", "Price/demand correlation", "number", -0.35, advanced=True, min=-1, max=1),
            ParamSpec("fixed_costs", "Fixed costs", "currency", 1_200_000, unit="USD"),
            ParamSpec("margin_floor", "Margin floor", "percent", 0.10),
            ParamSpec("n_sims", "Scenarios", "int", 20000, advanced=True),
        ],
        outputs=[
            {"key": "expected_gross_profit", "label": "Expected gross profit", "type": "currency"},
            {"key": "gross_profit_p10", "label": "Downside (P10)", "type": "currency"},
            {"key": "gross_profit_p90", "label": "Upside (P90)", "type": "currency"},
            {"key": "prob_margin_breach", "label": "Prob. margin below floor", "type": "percent"},
        ],
    )
)
