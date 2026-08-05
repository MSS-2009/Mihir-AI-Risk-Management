"""Industry pack data structures.

An industry is DATA. It names which engines run, with what parameters, under
what correlation structure, using what vocabulary. Adding a sixth industry means
writing one file in this package and touching no engine code.

The dependency direction is one-way: `industries` imports from `engines`, never
the reverse. A test enforces it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from engines.copula import BASELINE_CORRELATION, build_matrix, ensure_pd, require_pd
from engines.fair import Marginal


@dataclass(frozen=True)
class EngineBinding:
    """One engine, parameterized for one industry.

    `lef` and `magnitude` are calibrated at the pack's reference revenue and are
    scaled to the user's actual revenue at runtime.
    """

    engine: str                          # engine id, e.g. "third_party_failure"
    label: str                           # industry vocabulary, e.g. "Vendor failure"
    lef: tuple[float, float, float]      # (min, mode, max) events per year
    magnitude: tuple[float, float]       # (mode, P90) dollars per event
    description: str = ""                # what this models, in the user's words


@dataclass(frozen=True)
class Question:
    """One intake question, and the engine parameter it actually moves.

    If a question does not move a parameter it is context only, and it is
    labelled as such in the UI. A questionnaire whose answers change nothing
    would be theatre, which this product cannot afford.
    """

    id: str
    label: str
    type: str                            # currency | percent | int | number | choice | text
    default: object = None
    unit: str | None = None
    help: str | None = None
    choices: list[str] | None = None
    # Modulation: which engine parameter this answer moves, and how.
    targets: list[str] = field(default_factory=list)   # engine ids
    rule: str | None = None              # modulation rule id, resolved in intake
    context_only: bool = False


@dataclass(frozen=True)
class IndustryPack:
    id: str
    name: str
    tagline: str
    reference_revenue: float
    bindings: list[EngineBinding]
    correlation_pairs: dict[tuple[str, str], float]
    questions: list[Question]
    vocabulary: dict[str, str] = field(default_factory=dict)
    baseline_correlation: float = BASELINE_CORRELATION

    # ---- derived ----

    @property
    def engine_keys(self) -> list[str]:
        return [b.engine for b in self.bindings]

    def marginals(self, revenue: float | None = None, alpha: float = 1.0) -> list[Marginal]:
        """Marginals scaled to the user's revenue.

        Magnitudes scale as (revenue / reference_revenue) ** alpha; frequencies
        stay flat with size. alpha=1.0 (proportional) is the v1 default and is
        exposed as a parameter so a sublinear exponent later is a config change
        rather than a refactor.
        """
        scale = 1.0
        if revenue and revenue > 0:
            scale = float((revenue / self.reference_revenue) ** alpha)
        return [
            Marginal(
                key=b.engine,
                label=b.label,
                lef=b.lef,
                magnitude=(b.magnitude[0] * scale, b.magnitude[1] * scale),
            )
            for b in self.bindings
        ]

    def matrix(self, overrides: dict[str, float] | None = None) -> tuple[np.ndarray, bool]:
        """(matrix, was_repaired).

        The authored matrix must be positive-definite and fails loudly if not.
        User overrides may leave the PD cone, so those are projected back and
        the repair is reported.
        """
        m = build_matrix(self.engine_keys, self.correlation_pairs, self.baseline_correlation)
        require_pd(m, self.id)
        if not overrides:
            return m, False
        idx = {k: i for i, k in enumerate(self.engine_keys)}
        m = m.copy()
        for pair, rho in overrides.items():
            a, b = pair.split("|")
            if a in idx and b in idx:
                m[idx[a], idx[b]] = m[idx[b], idx[a]] = float(np.clip(rho, -0.95, 0.95))
        return ensure_pd(m, f"{self.id} (user-adjusted)")

    def public(self) -> dict:
        """Serialized for GET /industries. Powers intake and the industry cards."""
        return {
            "id": self.id,
            "name": self.name,
            "tagline": self.tagline,
            "reference_revenue": self.reference_revenue,
            "engines": [
                {
                    "engine": b.engine,
                    "label": b.label,
                    "description": b.description,
                    "lef": list(b.lef),
                    "magnitude": list(b.magnitude),
                }
                for b in self.bindings
            ],
            "questions": [
                {
                    "id": q.id,
                    "label": q.label,
                    "type": q.type,
                    "default": q.default,
                    "unit": q.unit,
                    "help": q.help,
                    "choices": q.choices,
                    "targets": q.targets,
                    "rule": q.rule,
                    "context_only": q.context_only,
                }
                for q in self.questions
            ],
            "correlation": {
                "baseline": self.baseline_correlation,
                "pairs": [
                    {"a": a, "b": b, "rho": rho}
                    for (a, b), rho in self.correlation_pairs.items()
                ],
            },
            "vocabulary": self.vocabulary,
        }
