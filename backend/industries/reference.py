"""Reference data an operator would otherwise have to look up.

This is where the product knows something the user did not type in, which is
most of what separates an industry pack from a spreadsheet. Every table here is
deliberately small, deliberately hedged, and carries the basis for each figure
so the user can see what they are accepting.

The standard applied to all of it: being useful does not require being
authoritative. A distributor who sees their own HS chapter pre-filled with a
plausible duty rate, or a CRO that sees oncology carrying a higher screen-
failure rate than dermatology, recognises that the product knows their world.
They can then correct any figure in one click, and the audit trail records that
they did.

None of these are measured loss data or regulatory advice. Each table states
what it is and what it is not, and the value is surfaced with that caveat
attached rather than buried on a methodology page.
"""
from __future__ import annotations

# chapter -> (label, general duty rate, typical China Section 301 add-on)
HS_CHAPTERS: dict[str, tuple[str, float, float]] = {
    "8413": ("Pumps for liquids", 0.000, 0.25),
    "8414": ("Air/vacuum pumps, compressors, fans", 0.023, 0.25),
    "8421": ("Filtering and purifying machinery", 0.000, 0.25),
    "8431": ("Parts for lifting and earthmoving machinery", 0.000, 0.25),
    "8481": ("Taps, cocks, valves", 0.020, 0.25),
    "8482": ("Ball and roller bearings", 0.090, 0.25),
    "8483": ("Transmission shafts, gears, clutches", 0.025, 0.25),
    "8501": ("Electric motors and generators", 0.028, 0.25),
    "8504": ("Transformers and static converters", 0.016, 0.25),
    "8536": ("Electrical switching apparatus", 0.027, 0.075),
    "8537": ("Control panels and boards", 0.027, 0.25),
    "7307": ("Steel tube and pipe fittings", 0.043, 0.25),
    "7326": ("Other articles of iron or steel", 0.029, 0.25),
    "8207": ("Interchangeable tools", 0.043, 0.25),
    "9026": ("Flow, level and pressure instruments", 0.000, 0.25),
    "9032": ("Automatic regulating instruments", 0.017, 0.25),
}

# Origins where the Section 301 add-on applies to the chapters above.
SECTION_301_ORIGINS = {"china", "cn", "prc", "hong kong"}

DISCLAIMER = (
    "General US duty rates by HS chapter, shown as a starting reference. The rate "
    "that actually applies depends on the full ten-digit classification, country of "
    "origin, and any exclusions in force. Confirm with your customs broker before "
    "relying on it."
)


def duty_rate(hs_chapter: str, origin: str = "") -> tuple[float, str]:
    """(effective rate, explanation). Unknown chapters fall back to a mid rate."""
    key = (hs_chapter or "").strip()[:4]
    entry = HS_CHAPTERS.get(key)
    if not entry:
        return 0.03, "no chapter match, using a 3% placeholder"
    label, base, s301 = entry
    if (origin or "").strip().lower() in SECTION_301_ORIGINS:
        return base + s301, f"{label}: {base:.1%} general + {s301:.1%} Section 301 on China origin"
    return base, f"{label}: {base:.1%} general rate"


def chapters_public() -> list[dict]:
    return [
        {"chapter": k, "label": v[0], "general_rate": v[1], "section_301": v[2]}
        for k, v in HS_CHAPTERS.items()
    ]


# ---------------------------------------------------------------------------
# Automotive & manufacturing: what a commodity actually does to a budget.
# ---------------------------------------------------------------------------
# material -> (label, indicative annualized price volatility)
#
# A manufacturer knows what they buy. What turns that into a cost-shock
# parameter is how violently each input moves, which is the part they would
# otherwise have to ask a treasury desk for.
COMMODITY_VOLATILITY: dict[str, tuple[str, float]] = {
    "steel": ("Steel (hot-rolled coil)", 0.28),
    "aluminium": ("Aluminium", 0.22),
    "copper": ("Copper", 0.24),
    "resin": ("Resin and polymer", 0.20),
    "electronics": ("Electronics and semiconductors", 0.30),
    "rare_earth": ("Rare earth and permanent magnets", 0.35),
    "rubber": ("Rubber and elastomers", 0.25),
    "glass": ("Flat and safety glass", 0.12),
    "energy": ("Energy and utilities", 0.35),
    "freight": ("Inbound freight", 0.45),
    "other": ("Other purchased material", 0.18),
}

COMMODITY_DISCLAIMER = (
    "Indicative annualized price volatility by input class, used to size how far a "
    "cost shock can travel. These are order-of-magnitude figures for scaling, not a "
    "market forecast and not a hedging recommendation. Replace them with your own "
    "purchasing history where you have it."
)

# Launch stage is the single best predictor of where recall exposure sits: a
# programme in ramp has neither the field data nor the process stability of one
# that has been building for three years.
LAUNCH_STAGE_RISK: dict[str, tuple[str, float]] = {
    "Pre-launch": ("Pre-launch", 1.5),
    "Ramp": ("Ramp", 1.8),
    "Mature": ("Mature", 1.0),
    "End of life": ("End of life", 1.2),
}


def commodity_volatility(material: str) -> tuple[float, str]:
    """(volatility, explanation). Unknown inputs fall back to a mid figure."""
    key = (material or "").strip().lower().replace(" ", "_")
    entry = COMMODITY_VOLATILITY.get(key)
    if not entry:
        return 0.20, "no material match, using a 20% placeholder volatility"
    label, vol = entry
    return vol, f"{label}: {vol:.0%} indicative annualized volatility"


# ---------------------------------------------------------------------------
# Clinical research: why some trials enroll and others do not.
# ---------------------------------------------------------------------------
# area -> (label, typical screen-failure rate, enrollment difficulty multiplier)
#
# A CRO does not need to be told that oncology enrolls harder than dermatology.
# They need a product that already knows it, so the enrollment question becomes
# "which areas are you running" rather than "how likely is a delay".
THERAPEUTIC_AREAS: dict[str, tuple[str, float, float]] = {
    "Oncology": ("Oncology", 0.45, 1.60),
    "Rare disease": ("Rare disease", 0.35, 2.00),
    "Neurology": ("Neurology and CNS", 0.40, 1.40),
    "Psychiatry": ("Psychiatry", 0.45, 1.50),
    "Cardiology": ("Cardiology", 0.30, 1.10),
    "Endocrine": ("Endocrine and metabolic", 0.28, 1.00),
    "Respiratory": ("Respiratory", 0.30, 1.00),
    "Infectious disease": ("Infectious disease", 0.25, 0.90),
    "Ophthalmology": ("Ophthalmology", 0.25, 1.10),
    "Dermatology": ("Dermatology", 0.20, 0.70),
    "Vaccines": ("Vaccines", 0.15, 0.80),
}

# phase -> (label, relative cost of a month of delay)
PHASE_DELAY_COST: dict[str, tuple[str, float]] = {
    "Phase I": ("Phase I", 0.60),
    "Phase II": ("Phase II", 1.00),
    "Phase III": ("Phase III", 1.90),
    "Phase IV": ("Phase IV", 0.90),
}

CLINICAL_DISCLAIMER = (
    "Screen-failure rates and enrollment difficulty by therapeutic area are starting "
    "estimates used to weight your own enrollment gap. They are not published trial "
    "statistics, not specific to your protocol or geography, and not clinical or "
    "regulatory advice. Your own historical enrollment curves are better evidence and "
    "should replace them."
)


def therapeutic_profile(area: str) -> tuple[float, float, str]:
    """(screen-failure rate, difficulty multiplier, explanation)."""
    entry = THERAPEUTIC_AREAS.get((area or "").strip())
    if not entry:
        return 0.30, 1.0, "no area match, using a neutral enrollment profile"
    label, sf, diff = entry
    return sf, diff, f"{label}: {sf:.0%} typical screen failure, {diff:.2f}x enrollment difficulty"


def phase_delay_cost(phase: str) -> tuple[float, str]:
    entry = PHASE_DELAY_COST.get((phase or "").strip())
    if not entry:
        return 1.0, "no phase match, using a Phase II reference"
    label, mult = entry
    return mult, f"{label}: {mult:.2f}x the cost of a Phase II month of delay"


# ---------------------------------------------------------------------------
# Property & data analytics: what a record costs when it leaks, and where.
# ---------------------------------------------------------------------------
# regime -> (label, indicative response cost per record, regulatory severity)
#
# The jurisdiction a record sits in changes both what a breach costs to handle
# and what follows from a regulator. A data business holds records in several,
# so the blend is the number that matters and nobody computes it by hand.
PRIVACY_REGIMES: dict[str, tuple[str, float, float]] = {
    "US general": ("US, no statutory damages", 165.0, 1.00),
    "California": ("California, CCPA and CPRA", 260.0, 1.40),
    "Illinois": ("Illinois, BIPA biometric", 480.0, 1.80),
    "New York": ("New York, SHIELD Act", 175.0, 1.20),
    "EU or UK": ("EU and UK, GDPR", 190.0, 1.60),
    "Canada": ("Canada, PIPEDA", 150.0, 1.10),
    "Other": ("Other jurisdiction", 160.0, 1.00),
}

PRIVACY_DISCLAIMER = (
    "Per-record response cost and regulatory severity by jurisdiction are indicative "
    "planning figures for scaling a breach, not legal advice and not a prediction of "
    "any penalty. Actual exposure depends on the data types involved, whether "
    "statutory damages attach, and how the incident is handled. Confirm with counsel."
)

# How much a wrong output costs depends on what the customer does with it.
DECISION_AUTOMATION: dict[str, tuple[str, float]] = {
    "Advisory only": ("Advisory only", 0.55),
    "Reviewed before use": ("Reviewed before use", 0.80),
    "Acted on automatically": ("Acted on automatically", 1.70),
}


def privacy_regime(jurisdiction: str) -> tuple[float, float, str]:
    """(cost per record, regulatory severity, explanation)."""
    entry = PRIVACY_REGIMES.get((jurisdiction or "").strip())
    if not entry:
        return 160.0, 1.0, "no jurisdiction match, using a generic US figure"
    label, cost, sev = entry
    return cost, sev, f"{label}: about ${cost:,.0f} per record, {sev:.2f}x regulatory severity"


# ---------------------------------------------------------------------------
# Wealth management: the regime you are examined under.
# ---------------------------------------------------------------------------
# registration -> (label, indicative examinations per year, enforcement severity)
REGISTRATION_REGIMES: dict[str, tuple[str, float, float]] = {
    "RIA (SEC)": ("SEC-registered adviser", 0.25, 1.00),
    "RIA (state)": ("State-registered adviser", 0.33, 0.80),
    "Broker-dealer (FINRA)": ("FINRA member broker-dealer", 1.00, 1.40),
    "Dual registrant": ("Dual registrant", 1.00, 1.60),
    "Bank or trust": ("Bank or trust company", 0.50, 1.20),
}

WEALTH_DISCLAIMER = (
    "Examination frequency and enforcement severity by registration type are starting "
    "estimates used to weight compliance exposure. They are not a prediction of your "
    "examination cycle and not legal or compliance advice. Your own examination and "
    "deficiency history is better evidence."
)


def registration_regime(registration: str) -> tuple[float, float, str]:
    """(exams per year, enforcement severity, explanation)."""
    entry = REGISTRATION_REGIMES.get((registration or "").strip())
    if not entry:
        return 0.25, 1.0, "no registration match, using an SEC adviser reference"
    label, exams, sev = entry
    return exams, sev, f"{label}: about {exams:.2f} examinations a year, {sev:.2f}x severity"
