"""Model registry, the glass box.

Every simulation is a pure, seeded, deterministic function paired with a
``ModelSpec`` describing it in human terms. `GET /models` serialises these
specs, so the methodology page can never drift from the code that runs.

Rules every registered model obeys (spec §4):
  * deterministic: seeded RNG, same inputs -> byte-identical outputs
  * returns a central estimate, a range (P10/P90 or equivalent), and an
    explicit ``assumptions`` dict
  * never trims outliers, in risk, the tail is the product
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Optional


@dataclass
class ParamSpec:
    """One human-readable input. Drives the frontend's shared input layout, so
    a CFO sees 'Annual import value', never `annual_import_value`."""

    name: str
    label: str
    # currency | percent | int | number | entity_list | choice
    type: str
    default: Any
    unit: Optional[str] = None
    help: Optional[str] = None
    advanced: bool = False
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    # for type == "entity_list": the shape of each row
    fields: Optional[list[dict]] = None
    # for type == "choice"
    choices: Optional[list[str]] = None


@dataclass
class ModelSpec:
    key: str  # registry key, e.g. "tariff"
    name: str  # human name
    version: str  # semver; bump when the math changes
    domain: str  # risk domain label
    method: str  # one-sentence description of the computation
    fn: Callable  # the pure function
    params: list[ParamSpec] = field(default_factory=list)
    outputs: list[dict] = field(default_factory=list)  # highlighted result keys
    seed: int = 42
    # Meta-models (e.g. composite correlation) need domain results as input and
    # are not runnable from defaults; still listed on /models for the glass box.
    runnable: bool = True

    def defaults(self) -> dict:
        """The default parameter dict used when the caller supplies nothing."""
        return {p.name: p.default for p in self.params}

    def public(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "version": self.version,
            "domain": self.domain,
            "method": self.method,
            "seed": self.seed,
            "runnable": self.runnable,
            "docstring": (self.fn.__doc__ or "").strip(),
            "parameters": [asdict(p) for p in self.params],
            "outputs": self.outputs,
        }


MODEL_REGISTRY: dict[str, ModelSpec] = {}


def register(spec: ModelSpec) -> Callable:
    """Register a model and return its function (so it can be used as a decorator
    target or called directly)."""
    if spec.key in MODEL_REGISTRY:
        raise ValueError(f"Duplicate model key: {spec.key}")
    MODEL_REGISTRY[spec.key] = spec
    return spec.fn


def run(key: str, params: Optional[dict] = None) -> dict:
    """Dispatch: build the full param dict from defaults + overrides, run the
    validated function. The LLM selects `key` and supplies `params`; it never
    reaches the numerics."""
    spec = MODEL_REGISTRY[key]
    if not spec.runnable:
        raise ValueError(f"Model '{key}' needs domain results and is not runnable from defaults")
    args = spec.defaults()
    if params:
        args.update({k: v for k, v in params.items() if v is not None})
    out = spec.fn(**args)
    return out


def trace_for(key: str, output: dict) -> dict:
    """Traceability envelope (spec §4.6): which model, version, seed, sim count."""
    spec = MODEL_REGISTRY[key]
    return {
        "model": output.get("model", spec.key),
        "model_key": spec.key,
        "version": spec.version,
        "seed": spec.seed,
        "n_sims": output.get("assumptions", {}).get("n_sims"),
    }
