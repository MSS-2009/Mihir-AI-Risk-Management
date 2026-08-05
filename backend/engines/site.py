"""Site disruption

A physical location becoming unavailable. Covers a warehouse, a plant and a clinical trial site. More sites spread the exposure; a single site concentrates it.
"""
from .registry import EngineSpec, register_engine

ENGINE = register_engine(
    EngineSpec(
        key="site_disruption",
        default_label="Site outage",
        domain="Operations",
        method=(
            "PERT-distributed outage frequency times a lognormal cost per "
            "event, with site count modulating concentration."
        ),
        description=(
            "A warehouse, facility or trial site becomes unavailable."
        ),
        modulators=["site_count"],
    )
)
