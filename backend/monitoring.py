"""What changed between two assessments, and why.

The rule this module exists to enforce: **every alert states the cause, not
merely the effect.** Not "your P95 rose 14%", but "your P95 rose 14%, driven by
third-party failure frequency re-estimating from 0.42 to 0.68 after four late
deliveries from one vendor last quarter."

An alert without a cause is a notification, and notifications get muted. Once
they are muted the monitoring product has no users, which is the failure mode
that kills this whole direction. So `Change` carries a `cause` field and the
detector refuses to emit one without it.

Materiality is the second discipline. A finance leader who is told about a 2%
move will stop reading, so only movements someone would act on are surfaced, and
every threshold is configurable per organisation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class Thresholds:
    """What counts as worth interrupting someone for. All configurable."""

    expected_annual_loss: float = 0.10      # relative move
    tail_p95: float = 0.10                  # relative move
    contribution_share: float = 0.05        # absolute, in share points
    concentration: float = 0.30             # largest counterparty share
    alert_on_provenance_change: bool = True
    alert_on_fragility_reorder: bool = True

    def public(self) -> dict:
        return {
            "expected_annual_loss": self.expected_annual_loss,
            "tail_p95": self.tail_p95,
            "contribution_share": self.contribution_share,
            "concentration": self.concentration,
            "alert_on_provenance_change": self.alert_on_provenance_change,
            "alert_on_fragility_reorder": self.alert_on_fragility_reorder,
        }


@dataclass(frozen=True)
class Change:
    """One material movement, with what drove it."""

    kind: str                   # expected_annual_loss | tail | contribution | provenance | fragility | concentration
    headline: str               # the effect, in one sentence
    cause: str                  # WHY. Never empty; the detector refuses without it.
    severity: str = "notable"   # notable | significant
    before: float | None = None
    after: float | None = None
    relative: float | None = None
    engine: str = ""

    def public(self) -> dict:
        return {
            "kind": self.kind,
            "headline": self.headline,
            "cause": self.cause,
            "severity": self.severity,
            "before": self.before,
            "after": self.after,
            "relative": round(self.relative, 4) if self.relative is not None else None,
            "engine": self.engine,
        }


def _rel(before: float, after: float) -> float:
    return (after - before) / before if before else 0.0


def _money(x: float) -> str:
    return f"${x:,.0f}"


def _curve(assessment: dict) -> dict[int, float]:
    return {p["percentile"]: p["loss"] for p in assessment.get("exceedance_curve", [])}


def _params(assessment: dict) -> dict[tuple[str, str], dict]:
    est = assessment.get("estimation") or {}
    return {(p["engine"], p["parameter"]): p for p in est.get("parameters", [])}


def _parameter_causes(previous: dict, current: dict) -> list[str]:
    """Which parameters moved, phrased as the reason a number changed.

    This is what turns an effect into a cause. Without it an alert can only
    report that something moved, which is precisely the alert people mute.
    """
    before, after = _params(previous), _params(current)
    causes = []
    for key, now in after.items():
        was = before.get(key)
        if not was or was.get("value") is None or now.get("value") is None:
            continue
        if was["value"] == 0:
            continue
        move = _rel(was["value"], now["value"])
        if abs(move) < 0.05:
            continue
        engine, parameter = key
        detail = ""
        if now.get("n_observations"):
            detail = (
                f" after {now['n_observations']} observed "
                f"{'event' if now['n_observations'] == 1 else 'events'} over "
                f"{now['window_years']:.1f} years"
            )
        causes.append(
            f"{engine.replace('_', ' ')} {parameter} re-estimated from "
            f"{was['value']:.3g} to {now['value']:.3g}{detail}"
        )
    return causes


def detect_changes(
    previous: dict,
    current: dict,
    thresholds: Thresholds | None = None,
) -> list[Change]:
    """Every material movement between two assessments, each with its cause."""
    t = thresholds or Thresholds()
    changes: list[Change] = []
    causes = _parameter_causes(previous, current)
    # The general cause, used when a headline number moved but no single
    # parameter dominates. Stated honestly rather than invented.
    general = "; ".join(causes[:3]) if causes else (
        "no parameter changed materially, so this is sampling variation rather "
        "than a change in your risk"
    )

    # ---- expected annual loss ----
    b, a = previous.get("expected_annual_loss"), current.get("expected_annual_loss")
    if b and a:
        move = _rel(b, a)
        if abs(move) >= t.expected_annual_loss:
            changes.append(Change(
                kind="expected_annual_loss",
                headline=(
                    f"Expected annual loss {'rose' if move > 0 else 'fell'} "
                    f"{abs(move):.0%}, from {_money(b)} to {_money(a)}"
                ),
                cause=general,
                severity="significant" if abs(move) >= 2 * t.expected_annual_loss else "notable",
                before=b, after=a, relative=move,
            ))

    # ---- tail ----
    cb, ca = _curve(previous), _curve(current)
    if 95 in cb and 95 in ca:
        move = _rel(cb[95], ca[95])
        if abs(move) >= t.tail_p95:
            changes.append(Change(
                kind="tail",
                headline=(
                    f"The figure to plan against, P95, {'rose' if move > 0 else 'fell'} "
                    f"{abs(move):.0%}, from {_money(cb[95])} to {_money(ca[95])}"
                ),
                cause=general,
                severity="significant" if abs(move) >= 2 * t.tail_p95 else "notable",
                before=cb[95], after=ca[95], relative=move,
            ))

    # ---- who owns the loss ----
    before_share = {d["domain"]: d["base_share"] for d in previous.get("domain_contributions", [])}
    for d in current.get("domain_contributions", []):
        was = before_share.get(d["domain"])
        if was is None:
            continue
        delta = d["base_share"] - was
        if abs(delta) >= t.contribution_share:
            engine_causes = [c for c in causes if d["domain"].replace("_", " ") in c]
            if engine_causes:
                cause = engine_causes[0]
            elif delta < 0:
                # A share can fall while the exposure behind it is unchanged,
                # simply because other domains grew. Reporting that as a
                # reduction would read as good news about a risk that did not
                # improve, which is the most misleading thing this file could do.
                cause = (
                    "this exposure did not change; its share fell because other "
                    "domains grew around it"
                )
            else:
                cause = (
                    "this exposure did not change; its share rose because other "
                    "domains shrank around it"
                )
            changes.append(Change(
                kind="contribution",
                headline=(
                    f"{d['label']} now accounts for {d['base_share']:.0%} of expected loss, "
                    f"{'up' if delta > 0 else 'down'} {abs(delta) * 100:.0f} points from {was:.0%}"
                ),
                cause=cause,
                before=was, after=d["base_share"], relative=delta,
                engine=d["domain"],
            ))

    # ---- a parameter became measured ----
    if t.alert_on_provenance_change:
        pb, pa = _params(previous), _params(current)
        for key, now in pa.items():
            was = pb.get(key)
            if not was or was["provenance"] == now["provenance"]:
                continue
            rank = {"prior": 0, "blended": 1, "measured": 2}
            if rank.get(now["provenance"], 0) > rank.get(was["provenance"], 0):
                engine, parameter = key
                changes.append(Change(
                    kind="provenance",
                    headline=(
                        f"{engine.replace('_', ' ')} {parameter} is now "
                        f"{now['provenance']} rather than {was['provenance']}"
                    ),
                    cause=(
                        f"{now['n_observations']} observations over "
                        f"{now['window_years']:.1f} years now carry "
                        f"{now['weight_on_data']:.0%} of the estimate, from "
                        f"{now.get('source') or 'your connected data'}"
                    ),
                    engine=engine,
                ))

    return changes


def _fragility_top(robustness: dict) -> str:
    rows = (robustness or {}).get("dependence_fragility") or []
    return " and ".join(rows[0]["labels"]) if rows else ""


def detect_fragility_change(previous_rob: dict, current_rob: dict) -> Change | None:
    """The pair whose correlation the answer is most sensitive to.

    Worth its own alert because it changes what to watch, not what to do.
    """
    was, now = _fragility_top(previous_rob), _fragility_top(current_rob)
    if not was or not now or was == now:
        return None
    return Change(
        kind="fragility",
        headline=f"Your most fragile dependence is now {now}, was {was}",
        cause=(
            "the pair whose correlation moves your tail most has changed, so the "
            "relationship worth watching has changed with it"
        ),
    )


@dataclass
class MonitoringResult:
    changes: list[Change] = field(default_factory=list)
    checked_at: str = ""
    material: bool = False

    def public(self) -> dict:
        return {
            "checked_at": self.checked_at,
            "material": self.material,
            "changes": [c.public() for c in self.changes],
            "summary": (
                self.changes[0].headline if self.changes
                else "Nothing material changed since the last run."
            ),
        }


def compare_runs(
    previous: dict,
    current: dict,
    previous_robustness: dict | None = None,
    current_robustness: dict | None = None,
    thresholds: Thresholds | None = None,
) -> MonitoringResult:
    """The monitoring loop's output: what moved, why, and whether to interrupt."""
    changes = detect_changes(previous, current, thresholds)
    if previous_robustness and current_robustness:
        if (t := (thresholds or Thresholds())).alert_on_fragility_reorder:
            if (c := detect_fragility_change(previous_robustness, current_robustness)):
                changes.append(c)

    # Enforced, not assumed: an alert without a cause is a notification.
    for c in changes:
        assert c.cause, f"change '{c.kind}' has no cause and must not be sent"

    return MonitoringResult(
        changes=changes,
        checked_at=datetime.now(timezone.utc).isoformat(),
        material=bool(changes),
    )
