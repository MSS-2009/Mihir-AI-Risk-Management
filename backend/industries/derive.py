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

from .reference import (
    commodity_volatility,
    duty_rate,
    phase_delay_cost,
    privacy_regime,
    registration_regime,
    therapeutic_profile,
    DECISION_AUTOMATION,
    LAUNCH_STAGE_RISK,
)


def _num(x, default=0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


import math

# The most an entity-derived fact may move one parameter, in either direction.
# Matches the intake clamp, but is approached asymptotically rather than hit.
RESPONSE_LIMIT = 2.0
_LOG_LIMIT = math.log(RESPONSE_LIMIT)


def response(value: float, reference: float, damping: float = 1.0) -> float:
    """Multiplier for a fact against the value a representative book produces.

    Two properties matter here and neither is optional.

    A representative book must land on 1.0. The pack's published calibration
    describes a typical operator, so deriving from a typical book has to
    reproduce it. Otherwise the layer is not measuring anything, it is just
    adding a markup to everyone who fills in the form.

    An extreme book must not saturate. A hard clamp at 2.0 means a distributor
    at 25% duty and one at 40% see the same number, so editing the field stops
    doing anything, which is precisely the behaviour this layer exists to
    provide. Compressing in log space keeps the response bounded while leaving
    the slope non-zero everywhere, so every edit still registers.
    """
    if reference <= 0 or value <= 0:
        return 1.0
    return math.exp(_LOG_LIMIT * math.tanh(damping * math.log(value / reference) / _LOG_LIMIT))


def centered(share: float, reference: float, weight: float) -> float:
    """Multiplier for a share-style fact, neutral at the reference share.

    Used where the fact is already a proportion and a ratio would misbehave
    near zero.
    """
    return max(0.5, min(RESPONSE_LIMIT, 1.0 + (share - reference) * weight))


class Derivation:
    """Accumulates parameter changes with the evidence that produced each one.

    Every pack builds its adjustments the same way, and every adjustment has to
    carry the entity-level fact behind it. Without that the derivation layer is
    just a black box with better inputs, which is worse than asking the user
    for a percentage: at least they knew what that meant.
    """

    def __init__(self) -> None:
        self.mods: dict = {}
        self.trail: list[dict] = []

    def add(self, engine: str, modulation, why: str, evidence: str) -> None:
        if modulation.is_neutral:
            return
        self.mods[engine] = self.mods.get(engine, type(modulation)()).combine(modulation)
        self.trail.append({
            "source": "your book",
            "engine": engine,
            "reason": why,
            "evidence": evidence,
            "frequency_multiplier": round(modulation.frequency, 4),
            "magnitude_multiplier": round(modulation.magnitude, 4),
        })

    def result(self, facts: dict) -> tuple[dict, list[dict]]:
        facts["_modulations"] = self.mods
        return facts, self.trail


def _rows(entities, weight_field: str) -> list[dict]:
    """Rows that carry a positive weight. Everything else is noise in a table
    the user is still filling in."""
    return [e for e in (entities or []) if _num(e.get(weight_field)) > 0]


def _shares(rows: list[dict], weight_field: str) -> tuple[list[float], float]:
    w = [_num(r[weight_field]) for r in rows]
    total = sum(w)
    return ([x / total for x in w], total) if total else ([], 0.0)


def _hhi(shares: list[float]) -> float:
    return sum(s * s for s in shares)


def _top(rows: list[dict], shares: list[float]) -> tuple[dict, float]:
    i = max(range(len(rows)), key=lambda k: shares[k])
    return rows[i], shares[i]


def _weighted(rows: list[dict], shares: list[float], field: str, default: float) -> float:
    return sum(_num(r.get(field), default) * s for r, s in zip(rows, shares))


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


# ===========================================================================
# Automotive & manufacturing
# ===========================================================================


def derive_part_facts(parts: list[dict]) -> dict:
    """Concentration and fragility of the bill of materials.

    A manufacturer's exposure is not "how much do you spend with your biggest
    supplier". It is which specific parts stop the line, and a part stops the
    line when it is single-sourced with a long lead time and a poor quality
    record. That is three columns of their own data, not one percentage.
    """
    rows = _rows(parts, "annual_spend")
    if not rows:
        return {}
    shares, total = _shares(rows, "annual_spend")
    top, top_share = _top(rows, shares)

    single = [p for p in rows if p.get("single_source")]
    single_spend = sum(_num(p["annual_spend"]) for p in single)
    lead = _weighted(rows, shares, "lead_time_days", 30)
    ppm = _weighted(rows, shares, "ppm_defect", 50)

    # A part that is single-sourced AND long-lead is the one that actually
    # stops a build. Neither alone is the same problem.
    stoppers = [
        p for p in rows
        if p.get("single_source") and _num(p.get("lead_time_days"), 30) >= 45
    ]
    stopper_spend = sum(_num(p["annual_spend"]) for p in stoppers)

    return {
        "part_count": len(rows),
        "total_part_spend": round(total, 2),
        "part_hhi": round(_hhi(shares), 4),
        "effective_suppliers": round(1 / _hhi(shares), 2) if _hhi(shares) else None,
        "top_part": top.get("part") or top.get("name") or "your largest part",
        "top_part_supplier": top.get("supplier") or "your largest supplier",
        "top_part_share": round(top_share, 4),
        "top_part_lead_days": _num(top.get("lead_time_days"), 30),
        "single_source_parts": len(single),
        "single_source_spend_share": round(single_spend / total, 4) if total else 0.0,
        "weighted_lead_days": round(lead, 1),
        "weighted_ppm": round(ppm, 1),
        "line_stopper_count": len(stoppers),
        "line_stopper_share": round(stopper_spend / total, 4) if total else 0.0,
        "line_stopper_parts": [p.get("part") or p.get("name") for p in stoppers][:5],
        "parts_calculation": (
            "Concentration is the Herfindahl index of part spend. A line stopper is a "
            "single-sourced part on a lead time of 45 days or more. Lead time and "
            "defect rate are spend-weighted."
        ),
    }


def derive_program_facts(programs: list[dict]) -> dict:
    """Recall and warranty exposure from what is actually in production.

    Recall cost is units in the field times content value, weighted by where
    each programme sits in its life. A programme in ramp carries the exposure;
    one that has been building for three years mostly does not.
    """
    rows = _rows(programs, "annual_units")
    if not rows:
        return {}
    units = [_num(p["annual_units"]) for p in rows]
    total_units = sum(units)
    exposure, detail, weighted_risk = 0.0, [], 0.0

    for p, u in zip(rows, units):
        content = _num(p.get("content_value"), 0)
        stage = str(p.get("launch_stage") or "Mature")
        _label, mult = LAUNCH_STAGE_RISK.get(stage, ("Mature", 1.0))
        campaign = u * content
        exposure += campaign
        weighted_risk += mult * (u / total_units)
        detail.append({
            "program": p.get("name") or "programme",
            "annual_units": round(u, 0),
            "content_value": round(content, 2),
            "launch_stage": stage,
            "campaign_exposure": round(campaign, 2),
            "stage_multiplier": mult,
        })
    detail.sort(key=lambda r: -r["campaign_exposure"])

    ramping = [p.get("name") for p in rows
               if str(p.get("launch_stage")) in ("Pre-launch", "Ramp")]

    return {
        "program_count": len(rows),
        "total_annual_units": round(total_units, 0),
        "recall_exposure": round(exposure, 2),
        "top_program": detail[0]["program"],
        "top_program_exposure": detail[0]["campaign_exposure"],
        "weighted_launch_risk": round(weighted_risk, 3),
        "programs_in_ramp": ramping[:5],
        "program_detail": detail,
        "programs_calculation": (
            "Campaign exposure is annual units times content value per unit. Launch "
            "risk is unit-weighted across programmes, with ramp carrying the most."
        ),
    }


def derive_plant_facts(plants: list[dict]) -> dict:
    """What an hour of downtime costs, and where output is concentrated."""
    rows = _rows(plants, "output_share")
    if not rows:
        return {}
    shares, _total = _shares(rows, "output_share")
    top, top_share = _top(rows, shares)
    downtime = _weighted(rows, shares, "downtime_cost_per_hour", 40_000)
    return {
        "plant_count": len(rows),
        "top_plant": top.get("name") or "your primary plant",
        "top_plant_share": round(top_share, 4),
        "plant_hhi": round(_hhi(shares), 4),
        "weighted_downtime_cost": round(downtime, 2),
        "top_plant_downtime_cost": round(_num(top.get("downtime_cost_per_hour"), 40_000), 2),
        "plants_calculation": (
            "Output concentration is the Herfindahl index of plant shares. Downtime "
            "cost is output-weighted across plants."
        ),
    }


def derive_commodity_facts(commodities: list[dict]) -> dict:
    """Cost-shock exposure from what they buy and how much of it is fixed.

    The parameter is unhedged spend times how violently that input moves. Both
    halves come from somewhere: the spend from them, the volatility from us.
    """
    rows = _rows(commodities, "annual_spend")
    if not rows:
        return {}
    spend = [_num(c["annual_spend"]) for c in rows]
    total = sum(spend)
    unhedged_value, vol_weighted, detail = 0.0, 0.0, []

    for c, s in zip(rows, spend):
        vol, why = commodity_volatility(str(c.get("material") or ""))
        hedged = min(max(_num(c.get("hedged_share"), 0.0), 0.0), 1.0)
        open_spend = s * (1 - hedged)
        unhedged_value += open_spend
        vol_weighted += vol * open_spend
        detail.append({
            "material": c.get("material") or "input",
            "annual_spend": round(s, 2),
            "hedged_share": round(hedged, 4),
            "unhedged_spend": round(open_spend, 2),
            "volatility": vol,
            "swing_at_one_sigma": round(open_spend * vol, 2),
            "basis": why,
        })
    detail.sort(key=lambda r: -r["swing_at_one_sigma"])

    blended_vol = (vol_weighted / unhedged_value) if unhedged_value else 0.0
    return {
        "commodity_count": len(rows),
        "total_commodity_spend": round(total, 2),
        "unhedged_spend": round(unhedged_value, 2),
        "unhedged_share": round(unhedged_value / total, 4) if total else 0.0,
        "blended_volatility": round(blended_vol, 4),
        "one_sigma_swing": round(unhedged_value * blended_vol, 2),
        "top_commodity": detail[0]["material"] if detail else "",
        "commodity_detail": detail,
        "commodities_calculation": (
            "Unhedged spend is annual spend net of the share already fixed. The one-"
            "sigma swing is unhedged spend times the blended volatility of those "
            "inputs, weighted by unhedged value."
        ),
    }


def derive_all_automotive(answers: dict) -> dict:
    facts: dict = {}
    facts.update(derive_part_facts(answers.get("parts") or []))
    facts.update(derive_program_facts(answers.get("programs") or []))
    facts.update(derive_plant_facts(answers.get("plants") or []))
    facts.update(derive_commodity_facts(answers.get("commodities") or []))
    return facts


# ===========================================================================
# Clinical research & healthcare
# ===========================================================================


def derive_trial_facts(trials: list[dict]) -> dict:
    """Enrollment risk from the actual protocol book.

    A CRO's schedule exposure is the gap between where enrollment should be and
    where it is, weighted by how hard each therapeutic area is to recruit and
    what a month of delay costs at that phase. All of which they know, and none
    of which they should have to convert into a percentage themselves.
    """
    rows = _rows(trials, "annual_value")
    if not rows:
        return {}
    shares, total = _shares(rows, "annual_value")

    gap_weighted, difficulty_weighted, phase_weighted = 0.0, 0.0, 0.0
    total_sites, behind, detail = 0, [], []

    for t, s in zip(rows, shares):
        target = _num(t.get("target_enrollment"), 0)
        enrolled = _num(t.get("enrolled_to_date"), 0)
        # Shortfall against target, floored at zero: being ahead of plan is
        # good news but it does not offset a different trial running behind.
        gap = max(0.0, (target - enrolled) / target) if target > 0 else 0.0
        sf, difficulty, area_why = therapeutic_profile(str(t.get("therapeutic_area") or ""))
        phase_mult, phase_why = phase_delay_cost(str(t.get("phase") or ""))
        sites = int(_num(t.get("sites_activated"), 0))

        gap_weighted += gap * s
        difficulty_weighted += difficulty * s
        phase_weighted += phase_mult * s
        total_sites += sites
        if gap > 0.35:
            behind.append(t.get("name") or "a trial")
        detail.append({
            "trial": t.get("name") or "trial",
            "phase": t.get("phase"),
            "therapeutic_area": t.get("therapeutic_area"),
            "sponsor": t.get("sponsor"),
            "annual_value": round(_num(t["annual_value"]), 2),
            "enrollment_gap": round(gap, 4),
            "screen_failure": sf,
            "sites_activated": sites,
            "basis": f"{area_why}; {phase_why}",
        })
    detail.sort(key=lambda r: -r["annual_value"])

    # Sponsor concentration falls straight out of the trial book, so it never
    # needs to be asked as its own question.
    sponsors: dict[str, float] = {}
    for t, s in zip(rows, shares):
        name = str(t.get("sponsor") or "unnamed sponsor").strip()
        sponsors[name] = sponsors.get(name, 0.0) + s
    sponsor_shares = sorted(sponsors.items(), key=lambda kv: -kv[1])
    top_sponsor, top_sponsor_share = sponsor_shares[0]
    worst = max(detail, key=lambda r: r["enrollment_gap"])

    return {
        "trial_count": len(rows),
        "total_trial_value": round(total, 2),
        "weighted_enrollment_gap": round(gap_weighted, 4),
        "weighted_difficulty": round(difficulty_weighted, 3),
        "weighted_phase_cost": round(phase_weighted, 3),
        "sites_activated": total_sites,
        "trials_behind": behind[:5],
        "top_trial": detail[0]["trial"],
        "worst_gap_trial": worst["trial"],
        "worst_gap": round(worst["enrollment_gap"], 4),
        "worst_gap_area": worst["therapeutic_area"],
        "sponsor_count": len(sponsors),
        "sponsor_hhi": round(_hhi(list(sponsors.values())), 4),
        "top_sponsor": top_sponsor,
        "top_sponsor_share": round(top_sponsor_share, 4),
        "trial_detail": detail,
        "trials_calculation": (
            "Enrollment gap is shortfall against target, value-weighted across trials "
            "and scaled by therapeutic-area difficulty and phase delay cost. Sponsor "
            "concentration is the Herfindahl index of trial value by sponsor."
        ),
    }


def derive_data_system_facts(systems: list[dict]) -> dict:
    """Patient-data exposure from the systems that actually hold it."""
    rows = _rows(systems, "records")
    if not rows:
        return {}
    phi_rows = [s for s in rows if s.get("holds_phi")]
    phi_records = sum(_num(s["records"]) for s in phi_rows)
    total_records = sum(_num(s["records"]) for s in rows)
    vendor_hosted = [s for s in phi_rows if s.get("vendor_hosted")]
    vendor_records = sum(_num(s["records"]) for s in vendor_hosted)
    return {
        "system_count": len(rows),
        "total_records": round(total_records, 0),
        "phi_records": round(phi_records, 0),
        "phi_system_count": len(phi_rows),
        "vendor_hosted_phi_share": round(vendor_records / phi_records, 4) if phi_records else 0.0,
        "largest_phi_system": max(
            phi_rows, key=lambda s: _num(s["records"]), default={}
        ).get("name", "") if phi_rows else "",
        "systems_calculation": (
            "Patient-record exposure counts only systems flagged as holding PHI. "
            "Vendor-hosted share is the part of that sitting outside your own estate."
        ),
    }


def derive_all_clinical(answers: dict) -> dict:
    facts: dict = {}
    facts.update(derive_trial_facts(answers.get("trials") or []))
    facts.update(derive_data_system_facts(answers.get("data_systems") or []))
    return facts


# ===========================================================================
# Property & data analytics
# ===========================================================================


def derive_source_facts(sources: list[dict]) -> dict:
    """Upstream dependency risk from the feeds the product actually runs on."""
    rows = _rows(sources, "annual_cost")
    if not rows:
        return {}
    shares, total = _shares(rows, "annual_cost")
    core = [s for s in rows if str(s.get("criticality")) == "Core"]
    core_no_fallback = [s for s in core if not s.get("has_fallback")]
    no_fallback_cost = sum(_num(s["annual_cost"]) for s in core_no_fallback)
    top, top_share = _top(rows, shares)
    return {
        "source_count": len(rows),
        "total_source_cost": round(total, 2),
        "core_source_count": len(core),
        "unprotected_source_count": len(core_no_fallback),
        "unprotected_sources": [s.get("name") for s in core_no_fallback][:5],
        "unprotected_source_share": round(no_fallback_cost / total, 4) if total else 0.0,
        "top_source": top.get("name") or "your largest feed",
        "top_source_share": round(top_share, 4),
        "top_source_has_fallback": bool(top.get("has_fallback")),
        "sources_calculation": (
            "An unprotected source is one flagged Core with no fallback. Share is by "
            "annual cost, which is the best available proxy for how much of the "
            "product depends on it."
        ),
    }


def derive_model_facts(models: list[dict]) -> dict:
    """Model-error exposure from what the models decide and who checks them.

    The same accuracy means two different things depending on whether a human
    reviews the output. That is the column a data business can answer and a
    generic risk tool never asks for.
    """
    rows = _rows(models, "decisions_per_month")
    if not rows:
        return {}
    volume = [_num(m["decisions_per_month"]) for m in rows]
    total = sum(volume)
    shares = [v / total for v in volume]

    automation_weighted, error_weighted, detail = 0.0, 0.0, []
    for m, v, s in zip(rows, volume, shares):
        usage = str(m.get("usage") or "Reviewed before use")
        _label, mult = DECISION_AUTOMATION.get(usage, ("Reviewed before use", 0.80))
        mae = _num(m.get("error_rate"), 0.05)
        automation_weighted += mult * s
        error_weighted += mae * s
        detail.append({
            "model": m.get("name") or "model",
            "decisions_per_month": round(v, 0),
            "usage": usage,
            "error_rate": round(mae, 4),
            "automation_multiplier": mult,
            "exposed_decisions": round(v * mae, 0),
        })
    detail.sort(key=lambda r: -r["exposed_decisions"])

    automated = [m.get("name") for m in rows
                 if str(m.get("usage")) == "Acted on automatically"]
    return {
        "model_count": len(rows),
        "decisions_per_month": round(total, 0),
        "weighted_error_rate": round(error_weighted, 4),
        "weighted_automation": round(automation_weighted, 3),
        "wrong_decisions_per_month": round(total * error_weighted, 0),
        "automated_models": automated[:5],
        "top_model": detail[0]["model"],
        "model_detail": detail,
        "models_calculation": (
            "Exposed decisions are volume times error rate. Automation weighting "
            "raises exposure where output is acted on without review and lowers it "
            "where it is advisory."
        ),
    }


def derive_client_facts(clients: list[dict]) -> dict:
    """Revenue concentration from the contract book."""
    rows = _rows(clients, "annual_value")
    if not rows:
        return {}
    shares, total = _shares(rows, "annual_value")
    top, top_share = _top(rows, shares)
    renewing = [c for c in rows if _num(c.get("months_to_renewal"), 99) <= 12]
    renewing_value = sum(_num(c["annual_value"]) for c in renewing)
    return {
        "client_count": len(rows),
        "total_contract_value": round(total, 2),
        "client_hhi": round(_hhi(shares), 4),
        "effective_clients": round(1 / _hhi(shares), 2) if _hhi(shares) else None,
        "top_client": top.get("name") or "your largest client",
        "top_client_share": round(top_share, 4),
        "top_client_value": round(_num(top.get("annual_value")), 2),
        "renewing_within_year": len(renewing),
        "renewing_value_share": round(renewing_value / total, 4) if total else 0.0,
        "clients_calculation": (
            "Concentration is the Herfindahl index of annual contract value. Renewal "
            "exposure is the share of that value up for renewal inside twelve months."
        ),
    }


def derive_holdings_facts(holdings: list[dict]) -> dict:
    """Breach exposure from where the records actually sit."""
    rows = _rows(holdings, "records")
    if not rows:
        return {}
    shares, total = _shares(rows, "records")
    cost_weighted, severity_weighted, detail = 0.0, 0.0, []
    for h, s in zip(rows, shares):
        per_record, severity, why = privacy_regime(str(h.get("jurisdiction") or ""))
        cost_weighted += per_record * s
        severity_weighted += severity * s
        detail.append({
            "jurisdiction": h.get("jurisdiction"),
            "records": round(_num(h["records"]), 0),
            "cost_per_record": per_record,
            "exposure": round(_num(h["records"]) * per_record, 2),
            "basis": why,
        })
    detail.sort(key=lambda r: -r["exposure"])
    return {
        "jurisdiction_count": len(rows),
        "records_held": round(total, 0),
        "blended_cost_per_record": round(cost_weighted, 2),
        "blended_regulatory_severity": round(severity_weighted, 3),
        "notional_breach_exposure": round(total * cost_weighted, 2),
        "top_jurisdiction": detail[0]["jurisdiction"],
        "holdings_detail": detail,
        "holdings_calculation": (
            "Per-record cost and regulatory severity are blended across jurisdictions, "
            "weighted by how many records sit in each."
        ),
    }


def derive_all_property(answers: dict) -> dict:
    facts: dict = {}
    facts.update(derive_source_facts(answers.get("data_sources") or []))
    facts.update(derive_model_facts(answers.get("models") or []))
    facts.update(derive_client_facts(answers.get("clients") or []))
    facts.update(derive_holdings_facts(answers.get("data_holdings") or []))
    return facts


# ===========================================================================
# Wealth management & finance
# ===========================================================================


def derive_advisor_facts(advisors: list[dict]) -> dict:
    """Key-person risk, which is the risk in this business.

    A wealth manager's book walks out of the door with the advisor who owns the
    relationship. Concentration of AUM by advisor, and how much of it sits with
    someone near retirement, is the exposure nobody models and everybody knows.
    """
    rows = _rows(advisors, "book_aum")
    if not rows:
        return {}
    shares, total = _shares(rows, "book_aum")
    top, top_share = _top(rows, shares)
    retiring = [a for a in rows if a.get("retiring_5y")]
    retiring_aum = sum(_num(a["book_aum"]) for a in retiring)
    unsuccessioned = [a for a in retiring if not a.get("has_successor")]
    unsuccessioned_aum = sum(_num(a["book_aum"]) for a in unsuccessioned)
    return {
        "advisor_count": len(rows),
        "total_book_aum": round(total, 2),
        "advisor_hhi": round(_hhi(shares), 4),
        "top_advisor": top.get("name") or "your largest producer",
        "top_advisor_share": round(top_share, 4),
        "top_advisor_aum": round(_num(top.get("book_aum")), 2),
        "retiring_count": len(retiring),
        "retiring_aum_share": round(retiring_aum / total, 4) if total else 0.0,
        "unsuccessioned_count": len(unsuccessioned),
        "unsuccessioned_aum_share": round(unsuccessioned_aum / total, 4) if total else 0.0,
        "unsuccessioned_advisors": [a.get("name") for a in unsuccessioned][:5],
        "advisors_calculation": (
            "Key-person concentration is the Herfindahl index of AUM by advisor. "
            "Unsuccessioned AUM is the book held by advisors retiring within five "
            "years who have no named successor."
        ),
    }


def derive_relationship_facts(relationships: list[dict]) -> dict:
    """Fee revenue, market sensitivity and client concentration from the book."""
    rows = _rows(relationships, "aum")
    if not rows:
        return {}
    shares, total_aum = _shares(rows, "aum")
    top, top_share = _top(rows, shares)

    fee_revenue, market_linked_revenue, detail = 0.0, 0.0, []
    for r, s in zip(rows, shares):
        aum = _num(r["aum"])
        bps = _num(r.get("fee_bps"), 80)
        linked = min(max(_num(r.get("market_linked_share"), 1.0), 0.0), 1.0)
        rev = aum * bps / 10_000.0
        fee_revenue += rev
        market_linked_revenue += rev * linked
        detail.append({
            "relationship": r.get("name") or "relationship",
            "aum": round(aum, 2),
            "fee_bps": bps,
            "fee_revenue": round(rev, 2),
            "market_linked_share": round(linked, 4),
        })
    detail.sort(key=lambda r: -r["fee_revenue"])

    return {
        "relationship_count": len(rows),
        "total_aum": round(total_aum, 2),
        "fee_revenue": round(fee_revenue, 2),
        "blended_fee_bps": round(fee_revenue / total_aum * 10_000, 1) if total_aum else 0.0,
        "market_linked_share": round(market_linked_revenue / fee_revenue, 4) if fee_revenue else 0.0,
        # A 20% drawdown is the standard planning shock, and it is the number a
        # principal actually feels.
        "revenue_at_20pct_drawdown": round(market_linked_revenue * 0.20, 2),
        "client_hhi": round(_hhi(shares), 4),
        "top_client": top.get("name") or "your largest relationship",
        "top_client_share": round(top_share, 4),
        "top_client_aum": round(_num(top.get("aum")), 2),
        "relationship_detail": detail,
        "relationships_calculation": (
            "Fee revenue is AUM times fee basis points. Market-linked share is the "
            "part of that revenue moving with market levels, and the drawdown figure "
            "applies a 20% fall to it."
        ),
    }


def derive_platform_facts(platforms: list[dict]) -> dict:
    """Outage exposure from the platforms the practice runs on."""
    rows = _rows(platforms, "annual_cost")
    if not rows:
        return {}
    shares, total = _shares(rows, "annual_cost")
    critical = [p for p in rows if str(p.get("function")) in ("Custodian", "Portfolio accounting")]
    no_fallback = [p for p in rows if not p.get("has_fallback")]
    top, top_share = _top(rows, shares)
    return {
        "platform_count": len(rows),
        "total_platform_cost": round(total, 2),
        "critical_platform_count": len(critical),
        "no_fallback_count": len(no_fallback),
        "no_fallback_platforms": [p.get("name") for p in no_fallback][:5],
        "top_platform": top.get("name") or "your primary platform",
        "top_platform_share": round(top_share, 4),
        "platforms_calculation": (
            "Custodian and portfolio accounting are treated as critical because an "
            "outage in either stops the practice trading and reporting."
        ),
    }


def derive_all_wealth(answers: dict) -> dict:
    facts: dict = {}
    facts.update(derive_relationship_facts(answers.get("relationships") or []))
    facts.update(derive_advisor_facts(answers.get("advisors") or []))
    facts.update(derive_platform_facts(answers.get("platforms") or []))
    reg = str(answers.get("registration") or "")
    if reg:
        exams, severity, why = registration_regime(reg)
        facts.update({
            "registration": reg,
            "exams_per_year": exams,
            "enforcement_severity": severity,
            "registration_basis": why,
        })
    return facts
