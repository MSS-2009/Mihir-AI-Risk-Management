"""Qualitative signal checks, sanctions, key news.

These are NOT simulations and produce NO fabricated numbers. They surface
status flags (a match, a headline) and, where warranted, nudge a model input
(e.g. raise a country's disruption probability). Every signal is clearly
attributed and reversible. This honors the rule that the AI never invents
figures, a signal changes an assumption the user can see and edit, nothing more.

The watchlist here is a small illustrative demo set. In production this maps to
OFAC/consolidated screening lists and a news provider; that integration is
scaffolded, not built.
"""
from __future__ import annotations

# Illustrative demo watchlist only, not a real sanctions list.
_DEMO_SANCTIONS_COUNTRIES = {"russia", "iran", "north korea", "belarus", "syria"}
_DEMO_ELEVATED_COUNTRIES = {"china": 0.05, "myanmar": 0.10, "venezuela": 0.08}

# Illustrative headline signals keyed by country.
_DEMO_NEWS = {
    "china": {"headline": "Export-control tightening reported on precision components", "severity": "elevated"},
    "germany": {"headline": "Rail-freight labor action affecting inland transit", "severity": "watch"},
}


def scan_signals(extracts: list[dict]) -> dict:
    """Scan extracted supplier/country references for sanctions and news signals.

    Returns signal cards plus any suggested assumption nudges (which the user
    confirms before they take effect)."""
    countries = sorted({(e.get("country") or "").strip().lower()
                        for e in extracts if e.get("country")})
    suppliers = [(e.get("supplier_name") or "") for e in extracts if e.get("supplier_name")]

    signals = []
    nudges = {}

    for c in countries:
        if not c:
            continue
        if c in _DEMO_SANCTIONS_COUNTRIES:
            signals.append({
                "type": "sanctions",
                "severity": "critical",
                "subject": c.title(),
                "message": f"{c.title()} appears on the screening watchlist, review before transacting.",
                "simulated": False,
            })
        elif c in _DEMO_ELEVATED_COUNTRIES:
            bump = _DEMO_ELEVATED_COUNTRIES[c]
            signals.append({
                "type": "sanctions",
                "severity": "watch",
                "subject": c.title(),
                "message": f"{c.title()} carries elevated screening/export-control risk.",
                "suggested_nudge": {"country_disruption_prob_add": bump},
                "simulated": False,
            })
            nudges.setdefault("country", {})[c] = {"disruption_prob_add": bump}
        if c in _DEMO_NEWS:
            n = _DEMO_NEWS[c]
            signals.append({
                "type": "news",
                "severity": n["severity"],
                "subject": c.title(),
                "message": n["headline"],
                "simulated": False,
            })

    return {
        "signals": signals,
        "suggested_nudges": nudges,
        "scanned": {"countries": countries, "suppliers": suppliers},
        "disclaimer": "Signals are qualitative flags, not simulated figures. Demo watchlist only.",
    }
