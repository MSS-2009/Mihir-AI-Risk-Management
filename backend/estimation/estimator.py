"""Marginals estimated from a customer's own history, with provenance attached.

The claim v3 makes is that some parameters stop being our published judgment and
become measured from the customer's history. This module is where that becomes
either true or a marketing line, so it is deliberately conservative:

Provenance is per parameter, not per engine. Accounting data routinely supports
a frequency and says nothing about the magnitude, so an engine can honestly be
"how often, measured; how much, our estimate". Collapsing that to one label per
engine would overstate roughly half of what we produce.

Nothing observed means nothing changes. An engine with no observations returns
the pack's marginal untouched, which keeps the guarantee that connecting a
system carrying no relevant history does not move a single number.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from canonical import Book
from engines.fair import Marginal

from .frequency import (
    DEFAULT_PRIOR_STRENGTH_YEARS,
    estimate_frequency_triple,
    pert_mean,
)
from .magnitude import estimate_magnitude, to_magnitude_pair
from .observe import Observations, observe_all

# Where a weight on data crosses from one description to the next.
MEASURED_ABOVE = 0.70
BLENDED_ABOVE = 0.20


def provenance_for(weight_on_data: float, available: bool) -> str:
    if not available:
        return "prior"
    if weight_on_data > MEASURED_ABOVE:
        return "measured"
    if weight_on_data > BLENDED_ABOVE:
        return "blended"
    return "prior"


@dataclass(frozen=True)
class ParameterEstimate:
    """One parameter, its value, and everything needed to defend it."""

    engine: str
    parameter: str                       # "frequency" | "magnitude"
    provenance: str                      # measured | blended | prior
    n_observations: int = 0
    window_years: float = 0.0
    weight_on_data: float = 0.0
    credible_interval: tuple[float, float] | None = None
    source: str = ""
    reason: str = ""
    snapshot_id: str = ""
    prior_value: float | None = None
    value: float | None = None

    def public(self) -> dict:
        return {
            "engine": self.engine,
            "parameter": self.parameter,
            "provenance": self.provenance,
            "n_observations": self.n_observations,
            "window_years": round(self.window_years, 2),
            "weight_on_data": round(self.weight_on_data, 4),
            "credible_interval": (
                [round(self.credible_interval[0], 4), round(self.credible_interval[1], 4)]
                if self.credible_interval else None
            ),
            "source": self.source,
            "reason": self.reason,
            "snapshot_id": self.snapshot_id,
            "prior_value": round(self.prior_value, 4) if self.prior_value is not None else None,
            "value": round(self.value, 4) if self.value is not None else None,
        }


@dataclass
class EstimationResult:
    marginals: list[Marginal]
    estimates: list[ParameterEstimate] = field(default_factory=list)
    observations: dict[str, Observations] = field(default_factory=dict)
    snapshot: dict | None = None

    def weight_for(self, engine: str, parameter: str) -> float:
        for e in self.estimates:
            if e.engine == engine and e.parameter == parameter:
                return e.weight_on_data
        return 0.0

    @property
    def coverage(self) -> dict:
        """The headline a customer sees: how much of this is theirs.

        Counted over parameters rather than engines, because an engine with a
        measured frequency and a prior magnitude is genuinely half measured and
        reporting it as fully measured would overstate the product.
        """
        counts = {"measured": 0, "blended": 0, "prior": 0}
        for e in self.estimates:
            counts[e.provenance] = counts.get(e.provenance, 0) + 1
        total = sum(counts.values()) or 1
        return {
            **counts,
            "total": total,
            "measured_share": round(counts["measured"] / total, 3),
            # What a customer could connect to improve it.
            "unlocks": sorted({
                o.reason for o in self.observations.values()
                if not o.available and o.reason
            }),
        }

    def public(self) -> dict:
        return {
            "coverage": self.coverage,
            "parameters": [e.public() for e in self.estimates],
            "observations": [o.public() for o in self.observations.values()],
            "snapshot": self.snapshot,
            "basis": (
                "Frequencies are estimated with a Gamma-Poisson conjugate model and "
                "shrunk toward the published prior by observation length. A parameter "
                "with no observations returns the published estimate unchanged."
            ),
        }


def estimate_marginals(
    marginals: list[Marginal],
    book: Book | None,
    prior_strength_years: float = DEFAULT_PRIOR_STRENGTH_YEARS,
) -> EstimationResult:
    """Re-estimate what the book supports; leave the rest exactly as published.

    With `book=None` this is a no-op returning the input marginals unchanged,
    which is what keeps every unconnected assessment byte-identical to v2.
    """
    if book is None:
        return EstimationResult(marginals=marginals)

    observations = observe_all(book)
    snapshot_id = book.snapshot.id
    out: list[Marginal] = []
    estimates: list[ParameterEstimate] = []

    for m in marginals:
        obs = observations.get(m.key)
        lef, magnitude = m.lef, m.magnitude

        # ---- frequency ----
        if obs and obs.available and obs.years_observed > 0:
            lef, posterior = estimate_frequency_triple(
                m.lef, obs.n_events, obs.years_observed, prior_strength_years
            )
            estimates.append(ParameterEstimate(
                engine=m.key, parameter="frequency",
                provenance=provenance_for(posterior.weight_on_data, True),
                n_observations=obs.n_events,
                window_years=obs.years_observed,
                weight_on_data=posterior.weight_on_data,
                credible_interval=(posterior.ci_low, posterior.ci_high),
                source=obs.source,
                snapshot_id=snapshot_id,
                prior_value=posterior.prior_mean,
                value=posterior.mean,
            ))
        else:
            estimates.append(ParameterEstimate(
                engine=m.key, parameter="frequency", provenance="prior",
                reason=obs.reason if obs else "no observer for this engine",
                snapshot_id=snapshot_id,
                prior_value=pert_mean(m.lef), value=pert_mean(m.lef),
            ))

        # ---- magnitude ----
        # Almost always the prior: a ledger records what you paid a vendor, not
        # what their failure cost you.
        if obs and obs.available and obs.losses:
            prior_mode, prior_p90 = m.magnitude
            import math
            prior_mu = math.log(max(math.sqrt(prior_mode * prior_p90), 1e-9))
            post = estimate_magnitude(prior_mu, 1.0, obs.losses)
            magnitude = to_magnitude_pair(post, m.magnitude)
            estimates.append(ParameterEstimate(
                engine=m.key, parameter="magnitude",
                provenance=provenance_for(post.weight_on_data, True),
                n_observations=post.n_observations,
                window_years=obs.years_observed,
                weight_on_data=post.weight_on_data,
                source=obs.source, snapshot_id=snapshot_id,
                prior_value=prior_mode, value=magnitude[0],
            ))
        else:
            estimates.append(ParameterEstimate(
                engine=m.key, parameter="magnitude", provenance="prior",
                reason=(
                    "financial records show what was paid, not what a disruption cost"
                    if obs and obs.available else (obs.reason if obs else "")
                ),
                snapshot_id=snapshot_id,
                prior_value=m.magnitude[0], value=m.magnitude[0],
            ))

        out.append(Marginal(key=m.key, label=m.label, lef=lef, magnitude=magnitude))

    return EstimationResult(
        marginals=out,
        estimates=estimates,
        observations=observations,
        snapshot=book.public(),
    )
