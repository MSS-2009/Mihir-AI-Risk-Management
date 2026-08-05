"""Inventory stockout

Demand outrunning cover. Reported alongside days of cover, because that is the lever an operator actually controls.
"""
from .registry import EngineSpec, register_engine

ENGINE = register_engine(
    EngineSpec(
        key="inventory_stockout",
        default_label="Stockout",
        domain="Operations",
        method=(
            "PERT-distributed stockout frequency times a lognormal cost per "
            "event combining lost margin and expediting."
        ),
        description=(
            "Demand outruns available cover and you lose margin or pay to "
            "expedite."
        ),
        modulators=["days_of_cover"],
    )
)
