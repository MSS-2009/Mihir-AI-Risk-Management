"""Interpretation, the CFO narrative.

The AI interprets; it never invents numbers. The prompt forbids introducing any
figure not present in the model output. Without an API key we fall back to a
deterministic, range-preserving summary built from the model output itself.
"""
from __future__ import annotations

from llm import MODEL, client, extract_text
from models import MODEL_REGISTRY

from .state import RiskState


def _money(n) -> str:
    try:
        return f"${n:,.0f}"
    except (TypeError, ValueError):
        return str(n)


def _fallback(o: dict, key: str | None = None) -> str:
    """Deterministic narrative, never a point estimate without its range."""
    model = o.get("model", "")
    if model.startswith("tariff"):
        return (
            f"Rerouting is expected to change your {o['assumptions']['horizon_years']}-year landed "
            f"cost by {_money(o['net_savings_pv_expected'])} (range {_money(o['net_savings_pv_p10'])} to "
            f"{_money(o['net_savings_pv_p90'])}), with a {o['prob_reroute_beneficial'] * 100:.0f}% chance "
            f"of net benefit. Year-one tariff cost today is {_money(o['current_tariff_cost_year1'])}. "
            f"These are expected values under the stated tariff-volatility and discount assumptions; "
            f"a higher switching cost or smaller tariff gap erodes the benefit."
        )
    if model == "monte_carlo_var":
        return (
            f"{o['confidence'] * 100:.0f}% VaR over {o['horizon_days']} day(s) is "
            f"{_money(o['value_at_risk'])}; expected shortfall is {_money(o['conditional_var'])}. "
            f"Tail estimates under the volatility assumption, not worst cases."
        )
    # Generic: state each highlighted output with its range, from the registry spec.
    spec = MODEL_REGISTRY.get(key or "")
    lines = []
    if spec:
        for out in spec.outputs:
            v = o.get(out["key"])
            if v is None:
                continue
            if out.get("type") == "currency":
                lines.append(f"{out['label']}: {_money(v)}")
            elif out.get("type") == "percent":
                lines.append(f"{out['label']}: {v * 100:.0f}%")
            else:
                lines.append(f"{out['label']}: {v}")
    body = "; ".join(lines) if lines else "See the model output for details."
    return (
        f"{body}. These are expected values with an explicit range, computed under the "
        f"stated assumptions, treat the range, not the central figure, as the answer."
    )


def _portfolio_fallback(assessment: dict) -> str:
    comp = assessment.get("composite") or {}
    ranked = assessment.get("ranked", [])
    top = ranked[0] if ranked else None
    parts = []
    if comp and not comp.get("insufficient_domains"):
        parts.append(
            f"Across {len(comp.get('domains', []))} risk domains, your expected annual loss is "
            f"{_money(comp.get('expected_total_loss'))}, but the P95 tail is "
            f"{_money(comp.get('correlated_p95'))}, and {comp.get('amplification_pct', 0) * 100:.0f}% "
            f"worse together than if the risks moved independently "
            f"({_money(comp.get('independent_p95'))})."
        )
        if comp.get("top_pairs"):
            tp = comp["top_pairs"][0]
            parts.append(f"The compounding is driven mainly by {tp['a_label']} and {tp['b_label']} moving together.")
    if top:
        rs = top["output"].get("risk_summary", {})
        parts.append(
            f"Your largest standalone exposure is {top['name']} "
            f"(expected {_money(rs.get('expected_loss'))}, P95 {_money(rs.get('p95_loss'))})."
        )
    parts.append(
        "These are expected values with explicit ranges under the stated assumptions; "
        "raising a supplier's disruption probability or a correlation would move the tail most."
    )
    return " ".join(parts)


def portfolio_interpretation(assessment: dict) -> str:
    """CFO narrative over a full multi-domain assessment. States ranges, names
    what would move the tail, invents nothing."""
    if client is None:
        return _portfolio_fallback(assessment)
    comp = assessment.get("composite") or {}
    ranked = [
        {"domain": r["name"], "risk_summary": r["output"].get("risk_summary")}
        for r in assessment.get("ranked", [])
    ]
    facts = {"composite": comp, "domains": ranked}
    prompt = (
        "You are a risk analyst briefing a mid-market CFO. In 5-7 sentences, explain this "
        "multi-domain risk assessment in plain, decision-oriented language. Lead with the "
        "composite: expected total loss, the correlated P95 tail, and how much worse risks are "
        "together than apart. Name the largest standalone exposure and the assumptions that would "
        "move the tail. Be explicit that figures are expected values with ranges. Invent no numbers "
        "beyond those given. Do not use em dashes or en dashes anywhere; use commas, colons, or "
        f"periods instead.\n\nAssessment:\n{facts}"
    )
    try:
        m = client.messages.create(
            model=MODEL, max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        return extract_text(m) or _portfolio_fallback(assessment)
    except Exception as e:
        return _portfolio_fallback(assessment) + f"\n\n(Live AI unavailable: {e})"


def interpretation_node(s: RiskState) -> RiskState:
    o = s["model_output"]
    key = s.get("risk_type")
    prompt = (
        "You are a risk analyst. In 4-6 sentences, explain these simulation results to a "
        "mid-market CFO in plain, decision-oriented language. State the dollar figures, be explicit "
        "they are expected values with a range, and name the assumptions that would flip the "
        "conclusion. Invent no numbers beyond those given. Do not use em dashes or en dashes; use "
        f"commas, colons, or periods instead.\n\nResults:\n{o}"
    )
    if client is None:
        return {"interpretation": _fallback(o, key)}
    try:
        m = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = extract_text(m)
        return {"interpretation": text or _fallback(o, key)}
    except Exception as e:
        return {"interpretation": _fallback(o, key) + f"\n\n(Live AI unavailable: {e})"}
