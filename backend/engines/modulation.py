"""Intake modulation: how an answer changes a parameter.

A questionnaire whose answers do not move any number is theatre, and this
product cannot afford theatre. So every rule here is:

  * explicit      one named function, one documented effect
  * bounded       clamped, so no answer can produce an absurd model
  * published     surfaced in the assumptions panel and on the methodology page
  * honest        these are judgment-based adjustments, not fitted coefficients

Each rule returns MULTIPLIERS against the pack's starting estimate. A neutral
answer returns 1.0 and leaves the default untouched, so a user who skips the
questionnaire gets exactly the published pack calibration.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

# Clamps. No single answer may move a parameter more than this, in either
# direction. Judgment-based rules should nudge, never dominate.
MIN_MULT, MAX_MULT = 0.5, 2.0


def _clamp(x: float) -> float:
    return float(min(MAX_MULT, max(MIN_MULT, x)))


@dataclass(frozen=True)
class Modulation:
    """Multipliers applied to one engine's starting estimate."""

    frequency: float = 1.0    # scales the whole PERT triple
    magnitude: float = 1.0    # scales (mode, P90) together

    def combine(self, other: "Modulation") -> "Modulation":
        return Modulation(
            frequency=_clamp(self.frequency * other.frequency),
            magnitude=_clamp(self.magnitude * other.magnitude),
        )

    @property
    def is_neutral(self) -> bool:
        return self.frequency == 1.0 and self.magnitude == 1.0


# --------------------------------------------------------------------------
# Rules. Each takes the answer and the question's default, returns a Modulation.
# --------------------------------------------------------------------------

MATURITY_SCALES = {
    # Higher maturity lowers how often an incident becomes a loss event.
    "Initial": 1.5, "Developing": 1.2, "Defined": 1.0, "Managed": 0.8, "Optimizing": 0.65,
    "Ad hoc": 1.4, "Periodic": 1.1, "Systematic": 0.85, "Continuous with holdout": 0.8,
    "Independently audited": 0.7, "Independently reviewed": 0.7,
    "Inconsistent": 1.35, "Standardised": 1.0, "Reviewed": 0.85,
    "Systematically audited": 0.7,
    "Simple": 0.8, "Moderate": 1.0, "Complex": 1.25, "Highly restrictive": 1.45,
    "Phase I": 0.7, "Phase II": 1.0, "Phase III": 1.4, "Phase IV": 1.1,
}


def _rel(answer, default) -> float:
    """Scale of `answer` relative to the question's own default.

    Anchoring on the default is what guarantees the documented contract: a user
    who accepts a pack default gets exactly the published calibration, never a
    silent adjustment.
    """
    a = MATURITY_SCALES.get(str(answer), 1.0)
    d = MATURITY_SCALES.get(str(default), 1.0)
    return a / d if d else 1.0


def control_maturity(answer, default) -> Modulation:
    """Stronger controls reduce loss-event FREQUENCY, not severity. A breach
    still costs what it costs; good controls make it rarer."""
    return Modulation(frequency=_clamp(_rel(answer, default)))


def process_maturity(answer, default) -> Modulation:
    """A systematic process catches failures earlier, reducing frequency and
    trimming severity because problems are caught smaller."""
    s = _rel(answer, default)
    return Modulation(frequency=_clamp(s), magnitude=_clamp(1.0 + (s - 1.0) * 0.4))


def process_maturity_inverse(answer, default) -> Modulation:
    """For questions where a 'higher' answer means MORE exposure (licensing
    complexity), rather than more maturity."""
    return process_maturity(answer, default)


def validation_maturity(answer, default) -> Modulation:
    """Validation intercepts wrong output before a customer acts on it, so it
    cuts frequency hard and severity moderately."""
    s = _rel(answer, default)
    return Modulation(frequency=_clamp(s), magnitude=_clamp(1.0 + (s - 1.0) * 0.5))


def concentration(answer, default) -> Modulation:
    """Concentration raises both terms: a concentrated relationship fails no
    more often on its own, but you feel it more, and you have less room to
    substitute so the event escalates more readily.

    Ratio against the pack default, damped: at twice the default share,
    frequency rises ~35% and magnitude ~70%.
    """
    a, d = float(answer or 0), float(default or 0)
    if d <= 0:
        return Modulation()
    r = a / d
    return Modulation(frequency=_clamp(1.0 + (r - 1.0) * 0.35), magnitude=_clamp(1.0 + (r - 1.0) * 0.70))


def exposure_share(answer, default) -> Modulation:
    """More exposed volume, proportionally more to lose. Magnitude only:
    exposure changes the size of the hit, not how often the shock occurs."""
    a, d = float(answer or 0), float(default or 0)
    if d <= 0:
        return Modulation()
    return Modulation(magnitude=_clamp(a / d))


def days_of_cover(answer, default) -> Modulation:
    """Cover is a buffer: more days absorb more delay before it becomes a
    stockout. Inverse and frequency-weighted, since cover mostly prevents the
    event rather than shrinking it."""
    a, d = float(answer or 0), float(default or 0)
    if a <= 0 or d <= 0:
        return Modulation()
    r = d / a
    return Modulation(frequency=_clamp(r), magnitude=_clamp(1.0 + (r - 1.0) * 0.35))


def buffer(answer, default) -> Modulation:
    """Running behind plan removes slack. Answer is a rate against plan, so
    below 1.0 means behind."""
    a, d = float(answer or 0), float(default or 0)
    if a <= 0 or d <= 0:
        return Modulation()
    return Modulation(frequency=_clamp(d / a))


def site_count(answer, default) -> Modulation:
    """More sites spread outage exposure: any one site matters less, though
    having more of them means an outage somewhere is a little more likely."""
    a, d = float(answer or 0), float(default or 0)
    if a <= 0 or d <= 0:
        return Modulation()
    return Modulation(frequency=_clamp((a / d) ** 0.5), magnitude=_clamp(d / a))


def site_count_inverse(answer, default) -> Modulation:
    """For dependency counts (data sources, platform vendors) where MORE
    dependencies means more exposure, not less."""
    a, d = float(answer or 0), float(default or 0)
    if a <= 0 or d <= 0:
        return Modulation()
    return Modulation(frequency=_clamp((a / d) ** 0.5))


def recall_history(answer, default) -> Modulation:
    """Your own event history is stronger evidence than any default. Anchored
    on the default count so a typical answer is neutral."""
    a, d = float(answer or 0), float(default or 0)
    return Modulation(frequency=_clamp((a + 1.0) / (d + 1.0)))


def records_held(answer, default) -> Modulation:
    """Breach magnitude scales with records held, sublinearly: per-record cost
    falls as volume rises (fixed response costs get spread)."""
    a, d = float(answer or 0), float(default or 0)
    if a <= 0 or d <= 0:
        return Modulation()
    return Modulation(magnitude=_clamp((a / d) ** 0.6))


def time_cost(answer, default) -> Modulation:
    """What an hour or a phase of delay is worth. Scales magnitude directly.

    Accepts either a currency answer (cost per hour) or a categorical one
    (trial phase), so the string branch has to come first.
    """
    if isinstance(answer, str):
        return Modulation(magnitude=_clamp(_rel(answer, default)))
    a, d = float(answer or 0), float(default or 0)
    if d <= 0:
        return Modulation()
    return Modulation(magnitude=_clamp(a / d))


def revenue_scale(answer, default) -> Modulation:
    """Handled by the pack's revenue scaling, not here, so this is a no-op.
    Kept as a named rule so the question can still declare its effect."""
    return Modulation()


def derived(answer, default) -> Modulation:
    """Marker rule: this question feeds the derivation layer rather than a
    multiplier. The industry computes the parameter change from the entities
    themselves, which is what makes a deep pack deep."""
    return Modulation()


RULES: dict[str, Callable] = {
    "derived": derived,
    "control_maturity": control_maturity,
    "process_maturity": process_maturity,
    "process_maturity_inverse": process_maturity_inverse,
    "validation_maturity": validation_maturity,
    "concentration": concentration,
    "exposure_share": exposure_share,
    "days_of_cover": days_of_cover,
    "buffer": buffer,
    "site_count": site_count,
    "site_count_inverse": site_count_inverse,
    "recall_history": recall_history,
    "records_held": records_held,
    "time_cost": time_cost,
    "revenue_scale": revenue_scale,
}

RULE_DESCRIPTIONS = {
    "derived": "Feeds the derivation layer: the parameter is computed from the entities you entered, not from a multiplier.",
    "control_maturity": "Stronger controls lower how often an incident becomes a loss event. Frequency only.",
    "process_maturity": "A systematic process catches failures earlier: lower frequency, and smaller when they happen.",
    "process_maturity_inverse": "More restrictive obligations create more ways to breach them.",
    "validation_maturity": "Validation intercepts wrong output before it is acted on.",
    "concentration": "Concentration raises both how often a relationship failure bites and what it costs.",
    "exposure_share": "More exposed volume means proportionally more to lose per event. Magnitude only.",
    "days_of_cover": "Cover absorbs delay before it becomes a stockout. Mostly prevents the event.",
    "buffer": "Running behind plan removes the slack that absorbs a delay.",
    "site_count": "More sites spread outage exposure; a single site concentrates it.",
    "site_count_inverse": "More upstream dependencies means more ways to be interrupted.",
    "recall_history": "Your own event history is stronger evidence than any default.",
    "records_held": "Breach magnitude scales with records held, sublinearly.",
    "time_cost": "What an hour or a phase of delay is actually worth to you.",
    "revenue_scale": "Scales every loss magnitude. Applied by revenue scaling, not as a multiplier.",
}


def damped(mod: "Modulation", keep: float) -> "Modulation":
    """Fade a multiplier toward neutral as measured evidence takes over.

    An intake answer and a measurement can describe the same thing twice. If a
    vendor-failure frequency has been estimated from purchase-order history,
    that history already contains whatever concentration the operator described
    in intake, and multiplying by it again counts the same fact twice.

    `keep` is `1 - weight_on_data`: with no measurement the answer applies in
    full, and as evidence accumulates the multiplier fades toward 1.0. Fading
    rather than switching avoids a cliff on the day a parameter crosses the
    "measured" threshold.
    """
    if keep >= 1.0:
        return mod
    k = max(0.0, min(1.0, keep))
    return Modulation(
        frequency=1.0 + (mod.frequency - 1.0) * k,
        magnitude=1.0 + (mod.magnitude - 1.0) * k,
    )


def apply_modulations(
    marginals: list, answers: dict, questions: list,
    damping: dict[str, float] | None = None,
) -> tuple[list, list[dict]]:
    """Apply intake answers to the pack's starting estimates.

    Returns (modulated marginals, audit trail). The audit trail is what makes
    this defensible: every adjustment is reported with the question that caused
    it, the rule that implemented it, and the exact multipliers applied.

    `damping` maps an engine to how much of the intake answer still applies,
    which is `1 - weight_on_data` from the estimator. Absent or empty, every
    answer applies in full and the result is identical to v2.
    """
    by_engine: dict[str, Modulation] = {}
    trail: list[dict] = []

    for q in questions:
        if q.context_only or not q.rule or q.rule not in RULES:
            continue
        if q.id not in answers or answers[q.id] is None:
            continue
        mod = RULES[q.rule](answers[q.id], q.default)
        if mod.is_neutral:
            continue
        targets = [m.key for m in marginals] if q.targets == ["*"] else q.targets
        applied = [t for t in targets if any(m.key == t for m in marginals)]
        if not applied:
            continue
        for t in applied:
            by_engine[t] = by_engine.get(t, Modulation()).combine(mod)
        trail.append(
            {
                "question": q.id,
                "label": q.label,
                "answer": answers[q.id],
                "default": q.default,
                "rule": q.rule,
                "rule_description": RULE_DESCRIPTIONS.get(q.rule, ""),
                "engines": applied,
                "frequency_multiplier": round(mod.frequency, 4),
                "magnitude_multiplier": round(mod.magnitude, 4),
            }
        )

    damping = damping or {}
    out = []
    for m in marginals:
        mod = by_engine.get(m.key)
        if mod is not None and m.key in damping:
            mod = damped(mod, damping[m.key])
        if not mod or mod.is_neutral:
            out.append(m)
            continue
        out.append(
            type(m)(
                key=m.key,
                label=m.label,
                lef=tuple(v * mod.frequency for v in m.lef),
                magnitude=(m.magnitude[0] * mod.magnitude, m.magnitude[1] * mod.magnitude),
            )
        )
    return out, trail
