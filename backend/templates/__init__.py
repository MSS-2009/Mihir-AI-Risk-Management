"""Template + accuracy registry (moat scaffold).

Merges the validated-template metadata with the live model registry so the
methodology page can show version, provenance, and tracked accuracy per model.
The template-authoring *pipeline* (AI drafts -> human review -> tests -> register)
is scaffolded behind FEATURES.template_authoring, not built.
"""
from __future__ import annotations

import json
import os

from features import FEATURES
from models import MODEL_REGISTRY

_PATH = os.path.join(os.path.dirname(__file__), "registry.json")


def _load() -> dict:
    with open(_PATH) as f:
        return json.load(f)


def templates_public() -> dict:
    data = _load()
    by_key = {t["model_key"]: t for t in data["templates"]}
    merged = []
    for key, spec in MODEL_REGISTRY.items():
        t = by_key.get(key)
        merged.append({
            "model_key": key,
            "name": spec.name,
            "version": spec.version,
            "runnable": spec.runnable,
            "status": t["status"] if t else "registered",
            "authored_by": t["authored_by"] if t else "human",
            "validated_on": t.get("validated_on") if t else None,
            "backtests": t.get("backtests") if t else None,
            "accuracy": t.get("accuracy") if t else None,
        })
    return {
        "templates": merged,
        "authoring_pipeline_enabled": FEATURES.template_authoring,
        "note": data["note"],
    }


def author_template(*_args, **_kwargs):
    """Scaffold: AI drafts a new model template for human review. Not built."""
    raise NotImplementedError(
        "Template authoring is scaffolded. Enable FEATURES.template_authoring and "
        "implement the draft -> review -> test -> register pipeline."
    )
