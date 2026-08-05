"""Regulatory compliance failure

A compliance, reporting or documentation failure and the remediation and penalty that follow. Deliberately excludes any claim about your regulator relationship, which this model cannot see.
"""
from .registry import EngineSpec, register_engine

ENGINE = register_engine(
    EngineSpec(
        key="regulatory_compliance_failure",
        default_label="Compliance failure",
        domain="Regulatory",
        method=(
            "PERT-distributed failure frequency times a lognormal cost per "
            "event covering remediation, penalty and rework."
        ),
        description=(
            "A compliance, reporting or documentation failure requiring "
            "remediation."
        ),
        modulators=["process_maturity"],
    )
)
