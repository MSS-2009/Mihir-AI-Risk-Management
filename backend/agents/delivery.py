"""Delivery, render the assessment in the format the user asked for.

Produces a structured document the frontend renders directly (executive summary,
one-pager, or list). Content is built deterministically from the model outputs
and the interpretation; the AI never introduces numbers here. Slide-deck and PDF
export are scaffolded (feature-flagged), not built.
"""
from __future__ import annotations

from domains import VALID_OUTPUT_FORMATS
from features import FEATURES


def _money(n) -> str:
    try:
        return f"${n:,.0f}"
    except (TypeError, ValueError):
        return str(n)


def _key_numbers(assessment: dict) -> list[dict]:
    comp = assessment.get("composite") or {}
    if comp.get("insufficient_domains") or not comp:
        return []
    return [
        {"label": "Expected annual loss", "value": _money(comp.get("expected_total_loss"))},
        {"label": "Composite tail (P95)", "value": _money(comp.get("correlated_p95"))},
        {"label": "Worse together than apart", "value": f"{comp.get('amplification_pct', 0) * 100:.0f}%"},
        {"label": "If risks were independent (P95)", "value": _money(comp.get("independent_p95"))},
    ]


def _domain_rows(assessment: dict) -> list[dict]:
    rows = []
    for r in assessment.get("ranked", []):
        rs = r["output"].get("risk_summary", {})
        rows.append({
            "domain": r["name"],
            "expected": _money(rs.get("expected_loss")),
            "tail_p95": _money(rs.get("p95_loss")),
        })
    return rows


def build_delivery(assessment: dict, interpretation: str, recommendations: list,
                   output_format: str = "executive_summary") -> dict:
    """Assemble the chosen deliverable. Always returns structured blocks; the
    caller/frontend renders them per format."""
    if output_format not in VALID_OUTPUT_FORMATS:
        output_format = "executive_summary"

    comp = assessment.get("composite") or {}
    headline = comp.get("headline") if not comp.get("insufficient_domains") else None
    recs = [
        {
            "rank": a["rank"],
            "title": a["title"],
            "domain": a["domain_name"],
            "impact": f"{_money(a.get('impact_expected'))} expected"
                      + (f", up to {_money(a.get('impact_tail'))} at P95" if a.get("impact_tail") else ""),
            "rationale": a["rationale"],
        }
        for a in recommendations
    ]

    doc = {
        "format": output_format,
        "title": "Enterprise risk assessment",
        "headline": headline,
        "key_numbers": _key_numbers(assessment),
        "interpretation": interpretation,
        "domain_table": _domain_rows(assessment),
        "recommendations": recs,
        "disclaimer": (
            "Figures are expected values with explicit ranges from seeded, "
            "deterministic simulations. Traceable to model, version, and seed."
        ),
    }

    if output_format == "list":
        doc["view"] = "list"
    elif output_format == "one_pager":
        doc["view"] = "compact"
        doc["recommendations"] = recs[:3]
    else:
        doc["view"] = "sections"

    doc["export"] = {
        "pdf": {"available": FEATURES.pdf_export, "tier": "Growth"},
        "slide_deck": {"available": FEATURES.slide_deck_export, "tier": "Growth"},
    }
    return doc
