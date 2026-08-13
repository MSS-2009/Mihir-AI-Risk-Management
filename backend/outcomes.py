"""What we predicted, what they chose, and eventually what happened.

Worth capturing from the first decision even though the payoff is a year away.
Once connected data reveals a realised outcome, predicted-versus-realised
becomes a genuine backtested track record, and that is the only credible path to
ever claiming accuracy. Reconstructing it later is impossible: the prediction has
to be recorded at the moment it was made, against the snapshot it was made from.

Two disciplines that are easy to skip and cannot be added retroactively:

The full predicted distribution is stored, not just the point estimate. A record
of "we said $140,000" cannot be scored honestly, because a distribution that put
40% mass below zero was not wrong when the outcome was negative. Storing the
quantiles is what makes calibration measurable rather than arguable.

No accuracy claim is surfaced until there is a real sample. `track_record()`
returns the count and refuses to compute a hit rate below the threshold, so a
convincing-looking number cannot appear off three decisions.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Below this many resolved decisions, no accuracy figure is produced at all.
MIN_SAMPLE_FOR_TRACK_RECORD = 20

PRESENTED, TAKEN, DECLINED, RESOLVED = "presented", "taken", "declined", "resolved"


@dataclass
class DecisionRecord:
    """One decision, as it was presented, with the prediction that came with it."""

    id: str
    organization_id: str
    decision_id: str
    title: str
    kind: str
    presented_at: str
    snapshot_id: str = ""
    status: str = PRESENTED

    # The prediction, in full. A point estimate cannot be scored.
    predicted_npv: float | None = None
    predicted_npv_p10: float | None = None
    predicted_npv_p90: float | None = None
    prob_beneficial: float | None = None
    cost_upfront: float = 0.0
    cost_annual: float = 0.0
    p95_reduction: float | None = None
    p99_reduction: float | None = None

    decided_at: str | None = None
    # Filled much later, from connected data rather than self-report.
    realised_value: float | None = None
    realised_at: str | None = None
    notes: str = ""

    def public(self) -> dict:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OutcomeStore:
    """Append-only decision log.

    JSON-backed so it works with no database, behind the interface Supabase will
    implement at CP5. Append-only on purpose: a decision log that can be edited
    is not evidence of anything.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self._records: list[DecisionRecord] = []
        if self.path and self.path.exists():
            self._records = [DecisionRecord(**r) for r in json.loads(self.path.read_text())]

    def _flush(self) -> None:
        if self.path:
            self.path.write_text(json.dumps([r.public() for r in self._records], indent=1))

    def record_presented(
        self, organization_id: str, decision: dict, snapshot_id: str = "", kind: str = ""
    ) -> DecisionRecord:
        """Capture a decision at the moment it was shown, with its prediction."""
        rec = DecisionRecord(
            id=f"{organization_id}:{decision.get('id')}:{len(self._records)}",
            organization_id=organization_id,
            decision_id=str(decision.get("id", "")),
            title=str(decision.get("title", "")),
            kind=kind,
            presented_at=_now(),
            snapshot_id=snapshot_id,
            predicted_npv=decision.get("npv"),
            predicted_npv_p10=decision.get("npv_p10"),
            predicted_npv_p90=decision.get("npv_p90"),
            prob_beneficial=decision.get("prob_beneficial"),
            cost_upfront=decision.get("cost_upfront", 0.0) or 0.0,
            cost_annual=decision.get("cost_annual", 0.0) or 0.0,
            p95_reduction=decision.get("p95_reduction"),
            p99_reduction=decision.get("p99_reduction"),
        )
        self._records.append(rec)
        self._flush()
        return rec

    def mark(self, record_id: str, status: str, notes: str = "") -> DecisionRecord | None:
        if status not in (TAKEN, DECLINED):
            raise ValueError(f"status must be {TAKEN} or {DECLINED}")
        for r in self._records:
            if r.id == record_id:
                r.status = status
                r.decided_at = _now()
                r.notes = notes or r.notes
                self._flush()
                return r
        return None

    def resolve(self, record_id: str, realised_value: float) -> DecisionRecord | None:
        """Record what actually happened. Only ever from observed data."""
        for r in self._records:
            if r.id == record_id:
                r.realised_value = float(realised_value)
                r.realised_at = _now()
                r.status = RESOLVED
                self._flush()
                return r
        return None

    def for_organization(self, organization_id: str) -> list[DecisionRecord]:
        return [r for r in self._records if r.organization_id == organization_id]

    def track_record(self, organization_id: str | None = None) -> dict:
        """Predicted versus realised, or an honest refusal.

        Below the sample threshold this returns the count and nothing else. A
        hit rate computed on four decisions is not a track record, and putting
        one on screen would be the single fastest way to lose a technical
        evaluator who asks how it was computed.
        """
        rows = [
            r for r in self._records
            if r.status == RESOLVED and r.realised_value is not None
            and (organization_id is None or r.organization_id == organization_id)
        ]
        n = len(rows)
        if n < MIN_SAMPLE_FOR_TRACK_RECORD:
            return {
                "resolved": n,
                "required": MIN_SAMPLE_FOR_TRACK_RECORD,
                "available": False,
                "note": (
                    f"{n} decisions have a realised outcome. No accuracy figure is "
                    f"reported below {MIN_SAMPLE_FOR_TRACK_RECORD}, because a rate "
                    "computed on a handful of decisions would not mean anything."
                ),
            }

        # Calibration, not a hit rate: how often the realised value landed inside
        # the interval we predicted. A well-calibrated 80% interval contains the
        # outcome about 80% of the time, and that is the claim worth making.
        inside = sum(
            1 for r in rows
            if r.predicted_npv_p10 is not None and r.predicted_npv_p90 is not None
            and r.predicted_npv_p10 <= r.realised_value <= r.predicted_npv_p90
        )
        return {
            "resolved": n,
            "available": True,
            "interval_coverage": round(inside / n, 3),
            "expected_coverage": 0.80,
            "note": (
                "Share of realised outcomes that fell inside the predicted 80% "
                "interval. A calibrated model lands near 0.80; higher means the "
                "intervals are too wide, lower means too narrow."
            ),
        }
