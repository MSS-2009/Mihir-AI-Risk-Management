"""Reference data a distributor would otherwise have to look up.

This is the first place the product knows something the user did not type in.
It is deliberately small and deliberately hedged.

HS duty rates below are general (column 1) US rates for the chapters that cover
most industrial equipment imports, plus the additional Section 301 rate that
applies to many China-origin goods in those chapters. They are a STARTING
REFERENCE, not a classification service: the legally operative rate depends on
the full ten-digit code, origin, and any exclusions in force. The UI says so and
asks the user to confirm with their broker.

Being useful here does not require being authoritative. A distributor who sees
their own chapter pre-filled with a plausible rate recognises the product knows
their world; they can then correct it in one click.
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
