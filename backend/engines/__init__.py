"""Industry-agnostic risk engines.

Nothing in this package may import from `industries`. Engines are pure
computation; industries are data that parameterizes them. A test enforces this.
"""
from .constants import DEFAULT_SEED, N_SIMS, N_SIMS_SWEEP
from .copula import (
    BASELINE_CORRELATION,
    COPULA_DF,
    CopulaDraws,
    build_matrix,
    draw_copula_inputs,
    ensure_pd,
    independent_uniforms,
    is_pd,
    nearest_pd,
    perturbed_matrix,
    require_pd,
    uniforms_for,
)
from .fair import (
    Marginal,
    closed_form_expected_loss,
    frequency_draws,
    lognormal_from_range,
    lognormal_mean,
    pert_mean,
    pert_samples,
    portfolio_losses,
)
from .registry import ENGINE_REGISTRY, EngineSpec, engines_public, get_engine

# Import side effects register the eleven engine identities.
from . import (  # noqa: E402,F401
    compliance,
    concentration,
    cyber,
    input_cost,
    inventory,
    model_error,
    recall,
    reputational,
    schedule,
    site,
    third_party,
)

__all__ = [
    "ENGINE_REGISTRY",
    "EngineSpec",
    "engines_public",
    "get_engine",
    "DEFAULT_SEED",
    "N_SIMS",
    "N_SIMS_SWEEP",
    "BASELINE_CORRELATION",
    "COPULA_DF",
    "CopulaDraws",
    "Marginal",
    "build_matrix",
    "closed_form_expected_loss",
    "draw_copula_inputs",
    "ensure_pd",
    "frequency_draws",
    "independent_uniforms",
    "is_pd",
    "lognormal_from_range",
    "lognormal_mean",
    "nearest_pd",
    "pert_mean",
    "pert_samples",
    "perturbed_matrix",
    "portfolio_losses",
    "require_pd",
    "uniforms_for",
]
