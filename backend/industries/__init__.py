"""INDUSTRY_REGISTRY. Adding an industry is a data change: write a pack module
and register it here. No engine code changes.
"""
from .base import EngineBinding, IndustryPack, Question
from .automotive import PACK as AUTOMOTIVE
from .clinical import PACK as CLINICAL
from .distribution import PACK as DISTRIBUTION
from .property_data import PACK as PROPERTY_DATA
from .wealth import PACK as WEALTH

# Display order for the industry selection screen.
INDUSTRY_REGISTRY: dict[str, IndustryPack] = {
    p.id: p for p in [
        AUTOMOTIVE,
        PROPERTY_DATA,
        CLINICAL,
        WEALTH,
        DISTRIBUTION,
    ]
}


def get_pack(industry_id: str) -> IndustryPack:
    if industry_id not in INDUSTRY_REGISTRY:
        raise KeyError(
            f"unknown industry '{industry_id}'. Available: {sorted(INDUSTRY_REGISTRY)}"
        )
    return INDUSTRY_REGISTRY[industry_id]


def industries_public() -> list[dict]:
    return [p.public() for p in INDUSTRY_REGISTRY.values()]


__all__ = [
    "INDUSTRY_REGISTRY",
    "EngineBinding",
    "IndustryPack",
    "Question",
    "get_pack",
    "industries_public",
]
