"""Cyber loss

A security or data incident that interrupts operations or exposes records. Frequency reflects how often an incident becomes a loss event rather than how often an attack is attempted.
"""
from .registry import EngineSpec, register_engine

ENGINE = register_engine(
    EngineSpec(
        key="cyber_loss",
        default_label="Cyber incident",
        domain="Cybersecurity",
        method=(
            "PERT-distributed loss-event frequency times a lognormal loss "
            "magnitude; stronger controls reduce frequency rather than "
            "severity."
        ),
        description=(
            "A security or data incident interrupts operations or exposes "
            "sensitive records."
        ),
        modulators=["control_maturity", "records_held"],
    )
)
