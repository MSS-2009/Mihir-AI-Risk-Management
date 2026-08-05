"""Counterparty concentration

The loss when a relationship you depend on lapses. Covers a major customer, a trial sponsor and a large client under stress; concentration raises both how often it bites and how much it costs.
"""
from .registry import EngineSpec, register_engine

ENGINE = register_engine(
    EngineSpec(
        key="counterparty_concentration",
        default_label="Customer concentration",
        domain="Counterparties",
        method=(
            "PERT-distributed lapse frequency times a lognormal revenue-at-risk "
            "magnitude, with concentration share modulating both."
        ),
        description=(
            "A customer, sponsor or client relationship you depend on lapses or "
            "materially shrinks."
        ),
        modulators=["concentration"],
    )
)
