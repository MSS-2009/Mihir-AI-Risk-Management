"""ENGINE_REGISTRY: the eleven engines, as identities over one shared core.

Under the FAIR structure every engine takes the same shape (a frequency triple
and a magnitude pair), so they share one sampler rather than reimplementing it
eleven times. What distinguishes an engine is not its math but its meaning:

  * what real-world event it represents
  * what an industry pack is allowed to call it
  * which intake answers may move its parameters
  * what derived metric, if any, is worth showing alongside the loss

Keeping them as separate registered identities also leaves room for an engine to
grow bespoke internals later (a real days-of-cover model for inventory, say)
without changing any caller.

Nothing here may import from `industries`. Engines are computation; industries
are data.
"""
from __future__ import annotations

from dataclasses import dataclass, field

VERSION = "1.0.0"


@dataclass(frozen=True)
class EngineSpec:
    key: str
    default_label: str          # used when a pack does not override the wording
    domain: str                 # grouping for the methodology page
    method: str                 # one sentence, shown on /models
    description: str            # what it models, in operator language
    modulators: list[str] = field(default_factory=list)  # intake rules that may move it
    version: str = VERSION

    def public(self) -> dict:
        return {
            "key": self.key,
            "name": self.default_label,
            "domain": self.domain,
            "version": self.version,
            "method": self.method,
            "description": self.description,
            "modulators": self.modulators,
            "parameters": [
                {"name": "lef", "label": "Event frequency (min, mode, max)", "type": "pert", "unit": "events/year"},
                {"name": "magnitude", "label": "Loss per event (mode, P90)", "type": "lognormal", "unit": "USD"},
            ],
            "basis": (
                "Starting estimate from expert judgment, not measured loss data. "
                "Editable, and the sensitivity output shows whether it matters."
            ),
        }


ENGINE_REGISTRY: dict[str, EngineSpec] = {}


def register_engine(spec: EngineSpec) -> EngineSpec:
    if spec.key in ENGINE_REGISTRY:
        raise ValueError(f"duplicate engine key: {spec.key}")
    ENGINE_REGISTRY[spec.key] = spec
    return spec


def get_engine(key: str) -> EngineSpec:
    if key not in ENGINE_REGISTRY:
        raise KeyError(f"unknown engine '{key}'. Available: {sorted(ENGINE_REGISTRY)}")
    return ENGINE_REGISTRY[key]


def engines_public() -> list[dict]:
    return [s.public() for s in ENGINE_REGISTRY.values()]
