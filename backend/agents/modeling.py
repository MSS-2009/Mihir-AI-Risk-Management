"""Modeling, dispatch to the validated model library.

The node reads the selected model key + params off the state and runs the pure
function. It attaches a traceability envelope (model, version, seed) alongside
the numbers, never inside them, so results stay reproducible and auditable.
"""
from __future__ import annotations

from models import MODEL_REGISTRY, run, trace_for

from .state import RiskState


def modeling_node(s: RiskState) -> RiskState:
    rt = s["risk_type"]
    if rt not in MODEL_REGISTRY:
        rt = "market"
    out = run(rt, s.get("params"))
    return {"model_output": out, "trace": trace_for(rt, out)}
