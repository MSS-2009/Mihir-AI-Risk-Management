"""Derive engine parameters from an operator's actual book.

The difference between a generic risk calculator and something built for a
distributor is where the numbers come from. Asking "what share of spend is with
your largest vendor?" is a question any CFO in any sector can answer. Taking
their vendor list and computing concentration, sole-source exposure, weighted
lead time and duty exposure is something only a product that understands their
business can do.

Everything here is arithmetic on what the user entered, so it stays inspectable:
each derived fact carries the calculation that produced it.
"""
from __future__ import annotations

from .reference import duty_rate


def _num(x, default=0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def derive_vendor_facts(vendors: list[dict]) -> dict:
    """Concentration, sole-source exposure and lead time from the vendor book."""
    rows = [v for v in (vendors or []) if _num(v.get("annual_spend")) > 0]
    if not rows:
        return {}
    spend = [_num(v["annual_spend"]) for v in rows]
    total = sum(spend)
    shares = [s / total for s in spend]
    hhi = sum(s * s for s in shares)

    top_i = max(range(len(rows)), key=lambda i: spend[i])
    sole = [v for v in rows if v.get("sole_source")]
    sole_spend = sum(_num(v["annual_spend"]) for v in sole)

    # Spend-weighted lead time: a long lead on a small line matters less.
    lead = sum(_num(v.get("lead_time_days"), 30) * s for v, s in zip(rows, shares))

    countries: dict[str, float] = {}
    for v, s in zip(rows, shares):
        countries[str(v.get("country") or "unknown").strip()] = (
            countries.get(str(v.get("country") or "unknown").strip(), 0.0) + s
        )
    top_country = max(countries.items(), key=lambda kv: kv[1]) if countries else ("unknown", 0.0)

    return {
        "vendor_count": len(rows),
        "total_vendor_spend": round(total, 2),
        "hhi": round(hhi, 4),
        "effective_vendors": round(1 / hhi, 2) if hhi else None,
        "top_vendor": rows[top_i].get("name") or "your largest vendor",
        "top_vendor_spend": round(spend[top_i], 2),
        "top_vendor_share": round(shares[top_i], 4),
        "top_vendor_sole_source": bool(rows[top_i].get("sole_source")),
        "top_vendor_country": rows[top_i].get("country") or "",
        "top_vendor_lead_days": _num(rows[top_i].get("lead_time_days"), 30),
        "sole_source_count": len(sole),
        "sole_source_share": round(sole_spend / total, 4) if total else 0.0,
        "weighted_lead_days": round(lead, 1),
        "top_country": top_country[0],
        "top_country_share": round(top_country[1], 4),
        "calculation": (
            "Concentration is the Herfindahl index of spend shares. Sole-source share is "
            "spend flagged single-source over total. Lead time is spend-weighted."
        ),
    }


def derive_sku_facts(lines: list[dict]) -> dict:
    """Duty exposure and cover from the product lines actually imported."""
    rows = [l for l in (lines or []) if _num(l.get("annual_import_value")) > 0]
    if not rows:
        return {}
    values = [_num(l["annual_import_value"]) for l in rows]
    total = sum(values)

    duty_cost, detail = 0.0, []
    for l, v in zip(rows, values):
        rate, why = duty_rate(str(l.get("hs_chapter") or ""), str(l.get("origin") or ""))
        duty_cost += v * rate
        detail.append(
            {
                "line": l.get("name") or l.get("hs_chapter") or "line",
                "hs_chapter": l.get("hs_chapter"),
                "origin": l.get("origin"),
                "import_value": round(v, 2),
                "duty_rate": round(rate, 4),
                "annual_duty": round(v * rate, 2),
                "basis": why,
            }
        )
    detail.sort(key=lambda r: -r["annual_duty"])

    cover = [(_num(l.get("days_of_cover"), 45), v) for l, v in zip(rows, values)]
    weighted_cover = sum(c * (v / total) for c, v in cover) if total else 0.0
    thin = [l.get("name") or l.get("hs_chapter") for l, (c, _v) in zip(rows, cover) if c < 30]

    return {
        "line_count": len(rows),
        "total_import_value": round(total, 2),
        "annual_duty_cost": round(duty_cost, 2),
        "blended_duty_rate": round(duty_cost / total, 4) if total else 0.0,
        "duty_by_line": detail,
        "weighted_days_of_cover": round(weighted_cover, 1),
        "thin_cover_lines": thin[:5],
        "calculation": (
            "Duty is each line's import value times the reference rate for its HS "
            "chapter and origin. Cover is import-value weighted."
        ),
    }


def derive_site_facts(sites: list[dict]) -> dict:
    """Throughput concentration across distribution centres."""
    rows = [s for s in (sites or []) if _num(s.get("throughput_share")) > 0]
    if not rows:
        return {}
    shares = [_num(s["throughput_share"]) for s in rows]
    total = sum(shares) or 1.0
    norm = [s / total for s in shares]
    top_i = max(range(len(rows)), key=lambda i: norm[i])
    return {
        "site_count": len(rows),
        "top_site": rows[top_i].get("name") or "your primary site",
        "top_site_share": round(norm[top_i], 4),
        "site_hhi": round(sum(s * s for s in norm), 4),
        "calculation": "Site concentration is the Herfindahl index of throughput shares.",
    }


def derive_all(answers: dict) -> dict:
    """Every derived fact, plus the flags a decision template can interpolate."""
    facts: dict = {}
    facts.update(derive_vendor_facts(answers.get("vendors") or []))
    facts.update(derive_sku_facts(answers.get("product_lines") or []))
    facts.update(derive_site_facts(answers.get("sites") or []))
    return facts
