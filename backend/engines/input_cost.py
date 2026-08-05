"""Input cost shock

An adverse move in the price of an input you must buy. Covers tariffs, duties and raw-material moves. It prices exposure to the move, not a forecast of the move itself.
"""
from .registry import EngineSpec, register_engine

ENGINE = register_engine(
    EngineSpec(
        key="input_cost_shock",
        default_label="Input cost shock",
        domain="Cost base",
        method=(
            "PERT-distributed shock frequency times a lognormal cost impact "
            "scaled by the share of spend exposed."
        ),
        description=(
            "Duties, tariffs or material prices move against you on volume you "
            "have to buy."
        ),
        modulators=["exposure_share"],
    )
)
