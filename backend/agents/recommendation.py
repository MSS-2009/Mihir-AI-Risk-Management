"""Recommendation, ranked actions, never a bare 'you should'.

Every action carries a dollar impact AND its range, drawn from the model
outputs. The AI orders and phrases; it introduces no figure not already
computed. Deterministic fallback when no key is present.
"""
from __future__ import annotations


def _money(n) -> str:
    try:
        return f"${n:,.0f}"
    except (TypeError, ValueError):
        return str(n)


# Per-domain action templates. Impact + range are pulled from the model output,
# never invented.
def _domain_actions(key: str, out: dict) -> list[dict]:
    rs = out.get("risk_summary", {})
    exp = rs.get("expected_loss")
    tail = rs.get("p95_loss")
    if key == "supplier_health":
        return [{
            "title": "Requalify a second source for your highest-risk supplier",
            "rationale": (
                f"Distress probability is {out.get('probability_of_distress', 0) * 100:.0f}% "
                f"(P10-P90 {out.get('pd_p10', 0) * 100:.0f}-{out.get('pd_p90', 0) * 100:.0f}%); "
                f"loss if it occurs is {_money(out.get('loss_given_distress'))}."
            ),
            "impact_expected": exp, "impact_tail": tail,
        }]
    if key == "supplier_concentration":
        return [{
            "title": "Reallocate spend away from your single-source concentration",
            "rationale": (
                f"HHI is {out.get('hhi')}, with {_money(out.get('single_source_spend_at_risk'))} "
                f"concentrated in {out.get('top_supplier')}."
            ),
            "impact_expected": exp, "impact_tail": tail,
        }]
    if key == "country":
        return [{
            "title": f"Diversify sourcing out of {out.get('worst_expected_country')}",
            "rationale": (
                f"{out.get('high_risk_spend_share', 0) * 100:.0f}% of spend sits in "
                f"high-risk geographies."
            ),
            "impact_expected": exp, "impact_tail": tail,
        }]
    if key == "delivery":
        return [{
            "title": "Raise inventory days-of-cover on the disruption-prone lane",
            "rationale": (
                f"Stockout probability is {out.get('prob_stockout', 0) * 100:.0f}%; "
                f"expected {out.get('expected_days_short')} days short."
            ),
            "impact_expected": exp, "impact_tail": tail,
        }]
    if key == "price":
        return [{
            "title": "Hedge or reprice to defend the margin floor",
            "rationale": (
                f"Margin falls below floor in {out.get('prob_margin_breach', 0) * 100:.0f}% of "
                f"scenarios; gross profit ranges {_money(out.get('gross_profit_p10'))} to "
                f"{_money(out.get('gross_profit_p90'))}."
            ),
            "impact_expected": exp, "impact_tail": tail,
        }]
    if key == "cyber":
        return [{
            "title": "Advance security control maturity one level",
            "rationale": (
                f"Breach probability is {out.get('prob_breach_this_year', 0) * 100:.0f}% at "
                f"maturity {out.get('control_maturity')}; a severe event costs "
                f"{_money(out.get('single_event_p95'))}."
            ),
            "impact_expected": exp, "impact_tail": tail,
        }]
    return []


def build_recommendations(assessment: dict) -> list[dict]:
    """Ranked actions across domains, worst tail first."""
    actions = []
    for key, payload in assessment.get("results", {}).items():
        for a in _domain_actions(key, payload["output"]):
            a["domain"] = key
            a["domain_name"] = payload.get("name", key)
            actions.append(a)
    actions.sort(key=lambda a: a.get("impact_tail") or 0, reverse=True)
    for i, a in enumerate(actions, 1):
        a["rank"] = i
    return actions
