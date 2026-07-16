"""Financial risk, market VaR and supplier financial health."""
import numpy as np

from ._util import beta_params, lin_distress, pctile, risk_summary
from .registry import ModelSpec, ParamSpec, register


def monte_carlo_var(
    portfolio_value,
    annual_return,
    annual_vol,
    horizon_days=1,
    confidence=0.95,
    n_sims=50000,
    seed=42,
):
    """Monte Carlo Value-at-Risk and Expected Shortfall.

    Draws horizon P&L under a Gaussian return assumption and reports the loss at
    the confidence quantile (VaR) plus the mean loss beyond it (conditional VaR).
    """
    rng = np.random.default_rng(seed)
    dt = horizon_days / 252
    pnl = portfolio_value * rng.normal(
        annual_return * dt, annual_vol * np.sqrt(dt), n_sims
    )
    var = -np.percentile(pnl, (1 - confidence) * 100)
    cvar = -pnl[pnl <= -var].mean() if (pnl <= -var).any() else var
    return {
        "model": "monte_carlo_var",
        "portfolio_value": portfolio_value,
        "horizon_days": horizon_days,
        "confidence": confidence,
        "value_at_risk": round(float(var), 2),
        "conditional_var": round(float(cvar), 2),
        "assumptions": {
            "annual_return": annual_return,
            "annual_vol": annual_vol,
            "n_sims": n_sims,
        },
    }


def supplier_financial_health(
    annual_spend,
    debt_to_equity=2.2,
    current_ratio=1.4,
    interest_coverage=2.5,
    profit_margin=0.03,
    payment_delinquency_days=25,
    industry_base_rate=0.03,
    loss_given_default=0.55,
    prior_strength=20.0,
    evidence_strength=12.0,
    n_sims=20000,
    seed=42,
):
    """Bayesian probability a key supplier hits financial distress, and the
    dollar exposure that creates.

    An Altman-inspired composite of leverage, liquidity, coverage, margin and
    payment behaviour produces a distress score in [0, 1]. That score is
    Bayesian evidence updating a Beta prior seeded at the industry base default
    rate, giving a *posterior distribution* over the supplier's 12-month
    probability of distress (not a single point). Monte Carlo then draws the
    distress event and a Beta loss-given-default to produce the annual-loss
    distribution. The credible interval on the probability is reported, never a
    bare point estimate.
    """
    rng = np.random.default_rng(seed)

    # Distress sub-scores: 0 = healthy reference, 1 = distressed reference.
    subs = {
        "leverage": (lin_distress(debt_to_equity, 1.0, 4.0), 0.25),
        "liquidity": (lin_distress(current_ratio, 2.0, 1.0), 0.20),
        "coverage": (lin_distress(interest_coverage, 6.0, 1.0), 0.25),
        "margin": (lin_distress(profit_margin, 0.10, -0.05), 0.20),
        "delinquency": (lin_distress(payment_delinquency_days, 0.0, 60.0), 0.10),
    }
    distress_score = sum(s * w for s, w in subs.values())

    # Conjugate Beta update: prior mean = industry base rate.
    a0, b0 = beta_params(industry_base_rate, prior_strength)
    a = a0 + distress_score * evidence_strength
    b = b0 + (1.0 - distress_score) * evidence_strength
    pd_samples = rng.beta(a, b, n_sims)  # posterior over probability of distress

    # Loss distribution: event ~ Bernoulli(pd), severity ~ Beta(LGD).
    default_event = (rng.random(n_sims) < pd_samples).astype(float)
    la, lb = beta_params(loss_given_default, 8.0)
    lgd = rng.beta(la, lb, n_sims)
    losses = default_event * annual_spend * lgd

    pd_mean = float(a / (a + b))
    return {
        "model": "supplier_financial_health_bayesian",
        "probability_of_distress": round(pd_mean, 4),
        "pd_p10": round(float(np.percentile(pd_samples, 10)), 4),
        "pd_p90": round(float(np.percentile(pd_samples, 90)), 4),
        "distress_score": round(float(distress_score), 3),
        "sub_scores": {k: round(s, 3) for k, (s, _w) in subs.items()},
        "exposure": round(float(annual_spend), 2),
        "loss_given_distress": round(float(annual_spend * loss_given_default), 2),
        "expected_annual_loss": round(float(losses.mean()), 2),
        "loss_p95": pctile(losses, 95),
        "loss_p99": pctile(losses, 99),
        "risk_summary": risk_summary(losses, "Supplier default"),
        "assumptions": {
            "annual_spend": annual_spend,
            "debt_to_equity": debt_to_equity,
            "current_ratio": current_ratio,
            "interest_coverage": interest_coverage,
            "profit_margin": profit_margin,
            "payment_delinquency_days": payment_delinquency_days,
            "industry_base_rate": industry_base_rate,
            "loss_given_default": loss_given_default,
            "prior_strength": prior_strength,
            "evidence_strength": evidence_strength,
            "n_sims": n_sims,
        },
    }


register(
    ModelSpec(
        key="market",
        name="Monte Carlo Value-at-Risk",
        version="1.0.0",
        domain="Financial markets",
        method=(
            "Draws horizon P&L under a Gaussian return assumption; reports the "
            "loss at the confidence quantile (VaR) and the mean loss beyond it "
            "(expected shortfall)."
        ),
        fn=monte_carlo_var,
        params=[
            ParamSpec("portfolio_value", "Portfolio value", "currency", 10_000_000, unit="USD"),
            ParamSpec("annual_return", "Expected annual return", "percent", 0.08),
            ParamSpec("annual_vol", "Annual volatility", "percent", 0.22),
            ParamSpec("horizon_days", "Horizon", "int", 1, unit="days", min=1, max=252),
            ParamSpec("confidence", "Confidence level", "percent", 0.95, advanced=True),
            ParamSpec("n_sims", "Scenarios", "int", 50000, advanced=True),
        ],
        outputs=[
            {"key": "value_at_risk", "label": "Value at Risk", "type": "currency"},
            {"key": "conditional_var", "label": "Expected shortfall", "type": "currency"},
        ],
    )
)


register(
    ModelSpec(
        key="supplier_health",
        name="Supplier financial health",
        version="1.0.0",
        domain="Supplier credit",
        method=(
            "Altman-inspired distress score updates a Beta prior at the industry "
            "base default rate (Bayesian), giving a posterior probability of "
            "distress; Monte Carlo over the distress event and loss-given-default "
            "yields the annual-loss distribution."
        ),
        fn=supplier_financial_health,
        params=[
            ParamSpec("annual_spend", "Annual spend with supplier", "currency", 4_200_000, unit="USD"),
            ParamSpec("debt_to_equity", "Debt-to-equity", "number", 2.2, help="Higher is riskier"),
            ParamSpec("current_ratio", "Current ratio", "number", 1.4, help="Current assets / current liabilities"),
            ParamSpec("interest_coverage", "Interest coverage", "number", 2.5, help="EBIT / interest expense"),
            ParamSpec("profit_margin", "Net profit margin", "percent", 0.03),
            ParamSpec("payment_delinquency_days", "Avg. payment delinquency", "int", 25, unit="days"),
            ParamSpec("industry_base_rate", "Industry base default rate", "percent", 0.03, advanced=True),
            ParamSpec("loss_given_default", "Loss given default", "percent", 0.55, advanced=True),
            ParamSpec("prior_strength", "Prior strength", "number", 20.0, advanced=True),
            ParamSpec("evidence_strength", "Evidence strength", "number", 12.0, advanced=True),
            ParamSpec("n_sims", "Scenarios", "int", 20000, advanced=True),
        ],
        outputs=[
            {"key": "probability_of_distress", "label": "Probability of distress (12mo)", "type": "percent"},
            {"key": "expected_annual_loss", "label": "Expected annual loss", "type": "currency"},
            {"key": "loss_p95", "label": "Tail loss (P95)", "type": "currency"},
            {"key": "loss_given_distress", "label": "Loss if distress occurs", "type": "currency"},
        ],
    )
)
