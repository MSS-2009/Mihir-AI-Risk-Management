"""Third-party failure

A critical external party stops delivering on the terms you planned around. The same engine covers a supplier, a vendor, an API provider and an outsourced site: what varies is the label and the parameters, not the mechanism.
"""
from .registry import EngineSpec, register_engine

ENGINE = register_engine(
    EngineSpec(
        key="third_party_failure",
        default_label="Supplier failure",
        domain="Third parties",
        method=(
            "PERT-distributed failure frequency times a lognormal loss per "
            "event, calibrated to the mode and 90th percentile of what one "
            "failure costs."
        ),
        description=(
            "A supplier, vendor or service provider you depend on cannot "
            "deliver on the terms you planned for."
        ),
        modulators=["concentration", "control_maturity"],
    )
)
