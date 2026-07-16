"""Intake, classify the request and select which model(s) to run.

Keyword routing is the deterministic fallback (and powers single /analyze). When
a key is present, `extract_intent` upgrades to a Claude structured-output call
over natural language ("we import $12M of housewares from China, mostly one
supplier") that selects domains and extracts parameters. The form/explicit path
always remains authoritative.
"""
from __future__ import annotations

import json

from domains import DEFAULT_DOMAINS, LOSS_DOMAINS
from llm import MODEL, client, extract_text

from .state import RiskState

_TARIFF_HINTS = ("tariff", "supply", "import", "sourcing", "reroute", "duty", "customs")


def classify(description: str) -> str:
    t = (description or "").lower()
    if any(k in t for k in _TARIFF_HINTS):
        return "tariff"
    return "market"


def intake_node(s: RiskState) -> RiskState:
    if s.get("risk_type"):
        rt = s["risk_type"]
    else:
        rt = classify(s.get("description", ""))
    return {"risk_type": rt}


def extract_intent(description: str, requested_domains=None) -> dict:
    """Return {domains, params_by_domain} for a multi-domain assessment.

    Explicit `requested_domains` win. Otherwise Claude extracts from natural
    language when available; the deterministic fallback is the full default set.
    """
    if requested_domains:
        return {"domains": [d for d in requested_domains if d in LOSS_DOMAINS] or DEFAULT_DOMAINS,
                "params_by_domain": {}, "source": "explicit"}
    if client is None or not (description or "").strip():
        return {"domains": DEFAULT_DOMAINS, "params_by_domain": {}, "source": "default"}

    prompt = (
        "You route a mid-market risk request to a fixed library of models and extract "
        "parameters. Return ONLY JSON: {\"domains\": [...], \"params_by_domain\": {model_key: {param: value}}}.\n"
        f"Valid model keys: {LOSS_DOMAINS}.\n"
        "Only include a param if the user stated it. Currency as plain numbers, rates as decimals.\n\n"
        f"Request: {description}"
    )
    try:
        m = client.messages.create(
            model=MODEL, max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = extract_text(m)
        raw = raw[raw.find("{"): raw.rfind("}") + 1]
        data = json.loads(raw)
        domains = [d for d in data.get("domains", []) if d in LOSS_DOMAINS] or DEFAULT_DOMAINS
        return {"domains": domains,
                "params_by_domain": data.get("params_by_domain", {}) or {},
                "source": "ai"}
    except Exception:
        return {"domains": DEFAULT_DOMAINS, "params_by_domain": {}, "source": "fallback"}
