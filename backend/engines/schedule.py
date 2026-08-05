"""Schedule disruption

Time slipping against a commitment. The same engine covers a production delay, a logistics delay and a clinical enrollment delay: the cost driver is elapsed time against a plan.
"""
from .registry import EngineSpec, register_engine

ENGINE = register_engine(
    EngineSpec(
        key="schedule_disruption",
        default_label="Schedule delay",
        domain="Operations",
        method=(
            "PERT-distributed delay-event frequency times a lognormal cost per "
            "event driven by delay duration and the cost of time."
        ),
        description=(
            "Production, logistics or enrollment slips against the schedule you "
            "committed to."
        ),
        modulators=["exposure_share", "buffer"],
    )
)
