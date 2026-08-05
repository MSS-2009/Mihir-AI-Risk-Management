"""Decision models, kept alongside the industry engines.

These answer a different question from the loss-exposure engines. An engine
prices what an exposure costs you per year; these evaluate a specific decision
("should we reroute?") or a market position. Section 4.8 keeps both.

RETIRED (2026-08-05): the six ad-hoc domain models that predated the industry
layer (supplier_health, supplier_concentration, delivery, country, price, cyber)
are no longer registered. They belonged to no industry pack, so listing them on
/models would advertise models the product cannot actually reach, which
undercuts the glass-box claim. Their source remains in git history.

supplier_health in particular is worth revisiting: its Bayesian distress score is
conceptually third_party_failure with a richer parameterization, and it may make
a better intake modulator than the flat default it replaced.
"""
from .registry import (
    MODEL_REGISTRY,
    ModelSpec,
    ParamSpec,
    register,
    run,
    trace_for,
)

# Import side effects register each model.
from . import tariff  # noqa: E402,F401
from . import financial  # noqa: E402,F401  (monte_carlo_var only)

__all__ = [
    "MODEL_REGISTRY",
    "ModelSpec",
    "ParamSpec",
    "register",
    "run",
    "trace_for",
]
