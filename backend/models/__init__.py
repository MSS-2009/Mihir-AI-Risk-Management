"""Model library. Importing this package registers every model in MODEL_REGISTRY."""
from .registry import (
    MODEL_REGISTRY,
    ModelSpec,
    ParamSpec,
    register,
    run,
    trace_for,
)

# Import side effects register each model. Order defines /models listing order.
from . import tariff  # noqa: E402,F401
from . import financial  # noqa: E402,F401  (market VaR + supplier health)
from . import supply_chain  # noqa: E402,F401
from . import country  # noqa: E402,F401
from . import pricing  # noqa: E402,F401
from . import cyber  # noqa: E402,F401
from . import composite  # noqa: E402,F401  (meta-model; runnable=False)

from .composite import composite_risk_correlation  # noqa: E402,F401

__all__ = [
    "MODEL_REGISTRY",
    "ModelSpec",
    "ParamSpec",
    "register",
    "run",
    "trace_for",
    "composite_risk_correlation",
]
