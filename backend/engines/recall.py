"""Product recall

A recall or warranty event. Deliberately low frequency with a heavy tail: recalls are rare and expensive, which is precisely the shape an average hides.
"""
from .registry import EngineSpec, register_engine

ENGINE = register_engine(
    EngineSpec(
        key="product_recall",
        default_label="Product recall",
        domain="Product",
        method=(
            "PERT-distributed recall frequency times a heavy-tailed lognormal "
            "cost per event covering recovery, replacement and warranty."
        ),
        description=(
            "A product defect triggers a recall or a wave of warranty claims."
        ),
        modulators=["recall_history"],
    )
)
