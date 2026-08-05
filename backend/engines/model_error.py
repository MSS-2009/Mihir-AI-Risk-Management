"""Model error

Shipping a materially wrong analytical output. The loss is the downstream decision made on it, plus remediation and credibility, not the cost of fixing the code.
"""
from .registry import EngineSpec, register_engine

ENGINE = register_engine(
    EngineSpec(
        key="model_error",
        default_label="Model error",
        domain="Analytics",
        method=(
            "PERT-distributed error frequency times a lognormal cost per event "
            "covering downstream decisions and remediation."
        ),
        description=(
            "A materially wrong analytical output reaches a customer and gets "
            "acted on."
        ),
        modulators=["validation_maturity"],
    )
)
