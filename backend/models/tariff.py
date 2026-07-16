"""Tariff & sourcing risk."""
import numpy as np

from .registry import ModelSpec, ParamSpec, register


def tariff_reroute_analysis(
    annual_import_value,
    current_tariff_rate,
    alt_tariff_rate,
    switching_cost,
    alt_unit_cost_delta=0.0,
    horizon_years=3,
    discount_rate=0.10,
    tariff_volatility=0.05,
    n_sims=10000,
    seed=42,
):
    """Monte Carlo: is rerouting sourcing worth it, in present-value dollars?

    Simulates tariff rates drifting under volatility over the horizon, discounts
    the resulting landed costs of the current vs alternative source, and reports
    the present-value savings distribution and probability that rerouting wins.
    """
    rng = np.random.default_rng(seed)
    horizon_years = int(horizon_years)
    yrs = np.arange(1, horizon_years + 1)
    disc = 1 / (1 + discount_rate) ** yrs

    def paths(base):
        drift = np.cumsum(
            rng.normal(0, tariff_volatility, (n_sims, horizon_years)), axis=1
        )
        return np.clip(base + drift, 0, None)

    goods_cur = annual_import_value
    goods_alt = annual_import_value * (1 + alt_unit_cost_delta)

    cur_pv = (goods_cur * (1 + paths(current_tariff_rate)) * disc).sum(axis=1)
    alt_pv = (goods_alt * (1 + paths(alt_tariff_rate)) * disc).sum(axis=1) + switching_cost
    sav = cur_pv - alt_pv

    return {
        "model": "tariff_reroute_montecarlo",
        "current_tariff_cost_year1": round(goods_cur * current_tariff_rate, 2),
        "current_landed_cost_pv": round(float(cur_pv.mean()), 2),
        "reroute_landed_cost_pv": round(float(alt_pv.mean()), 2),
        "net_savings_pv_expected": round(float(sav.mean()), 2),
        "net_savings_pv_p10": round(float(np.percentile(sav, 10)), 2),
        "net_savings_pv_p90": round(float(np.percentile(sav, 90)), 2),
        "prob_reroute_beneficial": round(float((sav > 0).mean()), 3),
        "assumptions": {
            "annual_import_value": annual_import_value,
            "current_tariff_rate": current_tariff_rate,
            "alt_tariff_rate": alt_tariff_rate,
            "switching_cost": switching_cost,
            "alt_unit_cost_delta": alt_unit_cost_delta,
            "horizon_years": horizon_years,
            "discount_rate": discount_rate,
            "tariff_volatility": tariff_volatility,
            "n_sims": n_sims,
        },
    }


register(
    ModelSpec(
        key="tariff",
        name="Tariff reroute analysis",
        version="1.0.0",
        domain="Tariffs & sourcing",
        method=(
            "Monte Carlo over tariff rates drifting under volatility; discounts "
            "current vs alternative landed cost to a present-value savings "
            "distribution and the probability rerouting is net-beneficial."
        ),
        fn=tariff_reroute_analysis,
        params=[
            ParamSpec("annual_import_value", "Annual import value", "currency", 8_000_000, unit="USD"),
            ParamSpec("current_tariff_rate", "Current tariff rate", "percent", 0.25),
            ParamSpec("alt_tariff_rate", "Alternative-source tariff rate", "percent", 0.07),
            ParamSpec("switching_cost", "Upfront switching cost", "currency", 750_000, unit="USD"),
            ParamSpec("alt_unit_cost_delta", "Added unit cost at new source", "percent", 0.04),
            ParamSpec("horizon_years", "Horizon", "int", 3, unit="years", min=1, max=10),
            ParamSpec("discount_rate", "Discount rate", "percent", 0.10, advanced=True),
            ParamSpec("tariff_volatility", "Tariff volatility", "percent", 0.05, advanced=True),
            ParamSpec("n_sims", "Scenarios", "int", 10000, advanced=True),
        ],
        outputs=[
            {"key": "net_savings_pv_expected", "label": "Expected 3-yr net savings", "type": "currency"},
            {"key": "net_savings_pv_p10", "label": "Downside (P10)", "type": "currency"},
            {"key": "net_savings_pv_p90", "label": "Upside (P90)", "type": "currency"},
            {"key": "prob_reroute_beneficial", "label": "Probability net-beneficial", "type": "percent"},
        ],
    )
)
