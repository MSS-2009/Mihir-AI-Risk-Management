"""What counts as an event, per engine, from a canonical book.

This module is where the honesty of the whole claim lives. Each function either
returns observations with the resource that evidenced them, or returns nothing
with a reason naming what the connection could not supply.

The reason matters more than it looks. "We found no late deliveries" and "this
connection cannot see promise dates" produce the same empty list and mean
opposite things: the first is evidence of a reliable supply chain, the second is
no evidence at all. Reporting the second as the first would hand a customer on a
thin connection a flattering number they did not earn.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from canonical import Book, Completeness, PromiseSource, Resource

# A delivery is "late" past this many days beyond a contracted promise. Below
# it, slippage is noise rather than a loss event.
LATE_THRESHOLD_DAYS = 14

# A customer counts as churned after this long with no revenue, having been
# material before. Two quarters: one is a gap, two is a departure.
CHURN_SILENCE_DAYS = 200

# Below this share of revenue a customer's loss is not a portfolio event.
CHURN_MATERIALITY = 0.01

# A repeat purchase whose unit price moves more than this is a cost shock.
PRICE_SHOCK_THRESHOLD = 0.15


@dataclass(frozen=True)
class Observations:
    """Events found for one engine, or the reason none could be."""

    engine: str
    n_events: int = 0
    years_observed: float = 0.0
    losses: list[float] = field(default_factory=list)
    source: str = ""
    available: bool = False
    reason: str = ""

    @classmethod
    def unavailable(cls, engine: str, reason: str) -> "Observations":
        return cls(engine=engine, available=False, reason=reason)

    def public(self) -> dict:
        return {
            "engine": self.engine,
            "n_events": self.n_events,
            "years_observed": round(self.years_observed, 2),
            "n_losses": len(self.losses),
            "source": self.source,
            "available": self.available,
            "reason": self.reason,
        }


def _needs(book: Book, resource: Resource, what: str) -> str | None:
    """Reason string when a resource cannot support a measurement, else None."""
    c = book.snapshot.completeness.get(resource, Completeness.ABSENT)
    if c is Completeness.ABSENT:
        return f"this connection does not supply {resource.value}, so {what} cannot be measured"
    return None


def observe_third_party_failure(book: Book) -> Observations:
    """Vendor failures: deliveries late against a contracted promise, or short.

    Requires promise dates. Most QuickBooks-grade connections do not carry them,
    which is the single biggest limit on what v3 can measure.
    """
    engine = "third_party_failure"
    if (r := _needs(book, Resource.PURCHASE_ORDERS, "vendor failure")):
        return Observations.unavailable(engine, r)

    contracted = [po for po in book.purchase_orders
                  if po.promise_source is PromiseSource.CONTRACT]
    if not contracted:
        return Observations.unavailable(
            engine,
            "purchase orders carry no vendor promise date, so a late delivery "
            "cannot be distinguished from a long lead time",
        )

    failures = [po for po in contracted
                if (po.days_late or 0) > LATE_THRESHOLD_DAYS or po.short_received]
    return Observations(
        engine=engine,
        n_events=len(failures),
        years_observed=book.snapshot.window_years,
        losses=[],   # the ledger never records what the failure cost
        source="purchase_orders",
        available=True,
    )


def observe_schedule_disruption(book: Book) -> Observations:
    """Delivery slippage. Falls back to lead-time dispersion when no promise
    date exists, because a lead time that varies wildly is itself evidence of
    schedule risk even without a commitment to measure against."""
    engine = "schedule_disruption"
    if (r := _needs(book, Resource.PURCHASE_ORDERS, "schedule disruption")):
        return Observations.unavailable(engine, r)

    contracted = [po for po in book.purchase_orders
                  if po.promise_source is PromiseSource.CONTRACT and po.days_late is not None]
    if contracted:
        late = [po for po in contracted if po.days_late > LATE_THRESHOLD_DAYS]
        return Observations(
            engine=engine, n_events=len(late),
            years_observed=book.snapshot.window_years,
            source="purchase_orders", available=True,
        )

    # No promise dates: use lead times that ran far beyond this vendor's own
    # typical. Weaker evidence, and labelled as such by the caller.
    leads = [po.lead_days for po in book.purchase_orders if po.lead_days is not None]
    if len(leads) < 12:
        return Observations.unavailable(
            engine, "too few completed purchase orders to characterise lead time")
    leads_sorted = sorted(leads)
    p90 = leads_sorted[int(len(leads_sorted) * 0.9)]
    excess = [x for x in leads if x > p90 + LATE_THRESHOLD_DAYS]
    return Observations(
        engine=engine, n_events=len(excess),
        years_observed=book.snapshot.window_years,
        source="purchase_orders (lead-time dispersion, no promise dates)",
        available=True,
    )


def observe_counterparty_concentration(book: Book) -> Observations:
    """Customer churn. The one engine where the LOSS is observable too: a
    departed customer's trailing revenue is exactly what was lost."""
    engine = "counterparty_concentration"
    if (r := _needs(book, Resource.INVOICES, "customer churn")):
        return Observations.unavailable(engine, r)
    if not book.engagements:
        return Observations.unavailable(engine, "no revenue history in this connection")

    end = book.snapshot.window_end
    totals: dict[str, float] = {}
    last: dict[str, object] = {}
    for e in book.engagements:
        totals[e.counterparty_id] = totals.get(e.counterparty_id, 0.0) + e.amount
        prev = last.get(e.counterparty_id)
        last[e.counterparty_id] = e.period_end if prev is None else max(prev, e.period_end)

    grand = sum(totals.values()) or 1.0
    years = max(book.snapshot.window_years, 1e-9)

    churned, losses = [], []
    for cid, total in totals.items():
        if total / grand < CHURN_MATERIALITY:
            continue                      # immaterial: not a portfolio event
        if end and (end - last[cid]).days > CHURN_SILENCE_DAYS:
            churned.append(cid)
            losses.append(total / years)  # trailing annual revenue lost

    return Observations(
        engine=engine, n_events=len(churned),
        years_observed=book.snapshot.window_years,
        losses=losses, source="invoices", available=True,
    )


def observe_input_cost_shock(book: Book) -> Observations:
    """Material moves in the unit price of a repeat purchase.

    Needs item-level unit prices, which accounting connections carry
    inconsistently. Without inventory or line detail this is unavailable rather
    than zero.
    """
    engine = "input_cost_shock"
    if (r := _needs(book, Resource.INVENTORY, "unit price movement")):
        return Observations.unavailable(
            engine,
            "this connection does not supply item-level unit prices, so repeat-"
            "purchase price movement cannot be measured",
        )
    if len(book.inventory) < 2:
        return Observations.unavailable(engine, "too few items to compare unit prices")

    # Inventory snapshots are point-in-time, so a single snapshot cannot show
    # movement. Honest answer until snapshot history accumulates.
    return Observations.unavailable(
        engine,
        "unit price movement needs at least two dated snapshots; this is the "
        "first, so there is nothing to compare against yet",
    )


def observe_inventory_stockout(book: Book) -> Observations:
    """Stockouts need inventory history, and one snapshot is not history.

    Counting SKUs currently at zero and dividing by the window would read a
    single instant as three years of evidence: a book that happens to be well
    stocked on the day we synced would report a stockout rate of zero and earn a
    reduction it never demonstrated. That is the same mistake as treating an
    absent resource as an empty one, only harder to see, so this stays
    unavailable until dated snapshots accumulate.
    """
    engine = "inventory_stockout"
    if (r := _needs(book, Resource.INVENTORY, "stockouts")):
        return Observations.unavailable(engine, r)
    if not book.inventory:
        return Observations.unavailable(engine, "no inventory records in this connection")
    return Observations.unavailable(
        engine,
        "stockout frequency needs inventory levels over time; this connection has "
        "one dated snapshot, and a single instant cannot evidence a rate",
    )


OBSERVERS = {
    "third_party_failure": observe_third_party_failure,
    "schedule_disruption": observe_schedule_disruption,
    "counterparty_concentration": observe_counterparty_concentration,
    "input_cost_shock": observe_input_cost_shock,
    "inventory_stockout": observe_inventory_stockout,
}

# Engines finance data cannot speak to at all. Named explicitly so the interface
# can say why rather than leaving a customer to wonder.
NOT_MEASURABLE = {
    "site_disruption": "physical site risk is not visible in financial records",
    "cyber_loss": "security incidents are not visible in financial records",
    "regulatory_compliance_failure": "compliance events are not visible in financial records",
    "product_recall": "recall events are not visible in financial records",
    "model_error": "model performance is not visible in financial records",
    "reputational_event": "reputational events are not visible in financial records",
}


def observe_all(book: Book) -> dict[str, Observations]:
    out = {k: fn(book) for k, fn in OBSERVERS.items()}
    for engine, reason in NOT_MEASURABLE.items():
        out[engine] = Observations.unavailable(engine, reason)
    return out
