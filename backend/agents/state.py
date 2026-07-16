"""Shared graph state. `total=False` so every field is optional and nodes only
write what they own."""
from __future__ import annotations

from typing import Any, TypedDict


class RiskState(TypedDict, total=False):
    # --- inputs ---
    description: str
    risk_type: str
    params: dict
    documents: list  # extracted document payloads (CP4)
    output_format: str  # executive_summary | one_pager | list (CP5)

    # --- intake ---
    selected_models: list  # [{key, params}] for multi-domain assess

    # --- document ---
    extracted: dict
    checklist: list
    signals: list

    # --- modeling ---
    model_output: dict
    trace: dict
    domain_results: dict  # key -> {output, trace} for /assess

    # --- correlation ---
    composite: dict

    # --- interpretation / recommendation / delivery ---
    interpretation: str
    recommendations: list
    delivery: dict

    # --- meta ---
    ai_enabled: bool
    notes: list[Any]
