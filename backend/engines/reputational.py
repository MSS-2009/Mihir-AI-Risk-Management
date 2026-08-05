"""Reputational event

A reputational incident and the revenue it costs. Modelled as its own domain where it is a primary exposure, and correlated with the domains that tend to trigger it elsewhere.
"""
from .registry import EngineSpec, register_engine

ENGINE = register_engine(
    EngineSpec(
        key="reputational_event",
        default_label="Reputational event",
        domain="Reputation",
        method=(
            "PERT-distributed incident frequency times a lognormal revenue "
            "impact from attrition and acquisition drag."
        ),
        description=(
            "An incident damages standing with clients or the market and costs "
            "revenue."
        ),
        modulators=["process_maturity"],
    )
)
