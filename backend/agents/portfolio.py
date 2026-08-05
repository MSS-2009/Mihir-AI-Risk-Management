"""Interpretation and recommendation over an industry assessment.

Both speak the pack's vocabulary: a clinical user reads "sites" and "sponsors",
a distributor reads "warehouses" and "vendors". Same engines underneath,
different words on screen, and never a mention of another industry's models.

The AI interprets; it never invents a figure. Both paths degrade to a
deterministic narrative when no API key is present.
"""
from __future__ import annotations

from llm import MODEL, client, extract_text

# Claim patterns that must never appear in generated copy. The bare word
# "accurate" is deliberately NOT banned: the methodology page legitimately needs
# to say that accuracy requires validation against realized losses.
BANNED_CLAIMS = (
    "industry benchmark",
    "based on industry data",
    "proven accuracy",
    "more accurate than",
    "industry-standard data",
    "empirically validated",
)


def check_claims(text: str) -> list[str]:
    """Return any banned claim patterns found. Used by tests and by the API."""
    low = text.lower()
    return [c for c in BANNED_CLAIMS if c in low]


def _money(n) -> str:
    try:
        return f"${n:,.0f}"
    except (TypeError, ValueError):
        return str(n)


def _facts(a: dict) -> dict:
    """Only the numbers the model actually produced. The prompt gets this and
    nothing else, so there is nothing else for the AI to cite."""
    P = {e["percentile"]: e["loss"] for e in a["exceedance_curve"]}
    return {
        "industry": a.get("industry_name", a["industry"]),
        "expected_annual_loss": a["expected_annual_loss"],
        "pct_of_revenue": a.get("expected_annual_loss_pct_revenue"),
        "p95": P.get(95),
        "p99": P.get(99),
        "correlation_premium_p99": a["correlation_premium"]["p99"],
        "joint_breach": a["joint_breach"],
        "domains": [
            {"label": d["label"], "base_share": d["base_share"], "tail_share": d["tail_share"]}
            for d in a["domain_contributions"]
        ],
        "top_sensitivity": [r["parameter_label"] for r in a.get("sensitivity", [])[:3]],
    }


def _fallback_narrative(a: dict) -> str:
    f = _facts(a)
    jb = f["joint_breach"]
    ratio = (
        jb["three_plus"] / jb["three_plus_independent"]
        if jb.get("three_plus_independent") else 0
    )
    top = f["domains"][0]["label"] if f["domains"] else "your largest domain"
    parts = [
        f"Across {len(f['domains'])} risk domains, expected annual loss is "
        f"{_money(f['expected_annual_loss'])}"
        + (f", about {f['pct_of_revenue']:.1%} of revenue" if f["pct_of_revenue"] else "")
        + f". The figure to plan against is the tail: {_money(f['p95'])} at P95 and "
        f"{_money(f['p99'])} at P99.",
        f"Treating these risks as independent would understate that P99 by "
        f"{f['correlation_premium_p99']:.0%}. Correlation does not change your average loss, "
        f"it changes the tail.",
        f"Three or more domains breach their own 90th percentile together in "
        f"{jb['three_plus']:.1%} of scenarios, against {jb['three_plus_independent']:.1%} "
        f"under independent modelling"
        + (f", roughly {ratio:.1f} times as often." if ratio else "."),
        f"{top} carries the largest share of the tail.",
    ]
    if f["top_sensitivity"]:
        parts.append(
            f"The answer moves most on {f['top_sensitivity'][0].lower()}, which is a starting "
            f"estimate you can adjust to your own experience."
        )
    return " ".join(parts)


def portfolio_interpretation(a: dict) -> str:
    """CFO narrative in the pack's vocabulary."""
    if client is None:
        return _fallback_narrative(a)
    prompt = (
        "You are a risk analyst briefing a mid-market operator in the "
        f"{a.get('industry_name', a['industry'])} sector. In 5 to 7 sentences, explain this "
        "assessment in plain, decision-oriented language.\n\n"
        "Rules you must follow:\n"
        "- Use ONLY the figures given below. Introduce no number that is not present.\n"
        "- Lead with expected annual loss, then the P95 and P99 tail.\n"
        "- State that correlation does not change the average, only the tail.\n"
        "- Name the domain carrying the most tail risk.\n"
        "- Describe the parameters as starting estimates the reader can adjust, never as "
        "industry benchmarks or measured data.\n"
        "- Do not mention any industry other than this one.\n"
        "- Do not use em dashes or en dashes. Use commas, colons or periods.\n\n"
        f"Figures:\n{_facts(a)}"
    )
    try:
        m = client.messages.create(
            model=MODEL, max_tokens=1200, messages=[{"role": "user", "content": prompt}]
        )
        text = extract_text(m)
        if not text or check_claims(text):
            return _fallback_narrative(a)
        return text
    except Exception:
        return _fallback_narrative(a)


# --------------------------------------------------------------------------
# Recommendations
# --------------------------------------------------------------------------

# What actually reduces each engine's exposure. Phrased as the lever an operator
# controls, not as the mechanism the model uses.
ACTIONS = {
    "third_party_failure": "Qualify a second source for your most concentrated dependency",
    "cyber_loss": "Advance security control maturity one level",
    "counterparty_concentration": "Reduce revenue concentration in your largest relationship",
    "regulatory_compliance_failure": "Move compliance review from periodic to systematic",
    "schedule_disruption": "Add buffer to the step that slips most often",
    "input_cost_shock": "Hedge or contract the exposed share of input spend",
    "inventory_stockout": "Raise days of cover on the lines that stock out",
    "site_disruption": "Establish failover for your most concentrated site",
    "product_recall": "Tighten pre-release validation on the highest-volume line",
    "model_error": "Move model validation to continuous with a holdout set",
    "reputational_event": "Formalise incident response and client communication",
}


def build_recommendations(a: dict) -> list[dict]:
    """Ranked actions, each with a dollar impact AND its range. Never a bare
    'you should': every row states what it is worth and how uncertain that is."""
    P = {e["percentile"]: e["loss"] for e in a["exceedance_curve"]}
    total_expected, total_tail = a["expected_annual_loss"], P.get(95, 0)
    rows = []
    for d in a["domain_contributions"]:
        engine = d["domain"]
        exp = total_expected * d["base_share"]
        tail = total_tail * d["tail_share"]
        rows.append(
            {
                "engine": engine,
                "domain_label": d["label"],
                "title": ACTIONS.get(engine, f"Reduce exposure in {d['label'].lower()}"),
                "expected_annual_exposure": round(exp, 2),
                "tail_exposure_p95": round(tail, 2),
                "tail_share": d["tail_share"],
                "rationale": (
                    f"{d['label']} is {d['base_share']:.0%} of expected loss and "
                    f"{d['tail_share']:.0%} of the P95 tail, so it is worth "
                    f"{_money(exp)} a year on average and up to {_money(tail)} in a bad year."
                ),
            }
        )
    rows.sort(key=lambda r: -r["tail_exposure_p95"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows
