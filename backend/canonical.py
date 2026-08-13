"""The canonical data model: one vocabulary, whatever the source system.

The most important structural decision in v3. Every connector normalises into
these records and nothing downstream sees anything else, so adding QuickBooks
after NetSuite is a mapping change and never an engine change. A test asserts
that no module under `engines/` or `industries/` imports from `connectors/`.

Three things here that the specification did not have, each of which exists
because the estimator would otherwise draw a wrong conclusion:

`Completeness` is per resource, not one number. The estimator has to tell "we
looked at your purchase orders and found no late deliveries" apart from "this
connection does not carry purchase orders". The first is evidence of a low rate.
The second is no evidence at all, and treating it as a zero would hand every
customer on a thin connection a flattering number they did not earn.

`PurchaseOrder.promise_source` records whether a promise date came from the
document or was inferred. Inferring a promise date from a typical lead time and
then measuring lateness against that inference is circular: it can only ever
report that deliveries arrive about when they usually arrive.

`Snapshot` is immutable. Corrections arrive as a new snapshot, never as an edit,
so any past assessment can be reproduced exactly from the snapshot it ran
against and "why did the number change" is answered by diffing two dated states.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class Resource(str, Enum):
    """What a connector can be asked for. One entry per canonical record type."""

    ACCOUNTS = "accounts"
    COUNTERPARTIES = "counterparties"
    INVOICES = "invoices"
    PURCHASE_ORDERS = "purchase_orders"
    EXPENSES = "expenses"
    CASH_POSITIONS = "cash_positions"
    INVENTORY = "inventory"


class Completeness(str, Enum):
    """What a connection actually returned for one resource.

    ABSENT is not a synonym for empty. A connection that cannot carry purchase
    orders reports ABSENT; a connection that carries them and found none reports
    FULL with zero records, which is a real observation of a quiet year.
    """

    FULL = "full"          # the resource is supported and was read completely
    PARTIAL = "partial"    # supported, but the window or fields are incomplete
    ABSENT = "absent"      # this connection cannot supply it at all


class PromiseSource(str, Enum):
    CONTRACT = "contract"   # the vendor committed to a date, in the record
    INFERRED = "inferred"   # we guessed it; never use for lateness measurement
    ABSENT = "absent"


@dataclass(frozen=True)
class Organization:
    id: str
    name: str
    industry_pack: str
    reference_revenue: float
    fiscal_year_end: str = "12-31"


@dataclass(frozen=True)
class Counterparty:
    id: str
    kind: str                      # customer | vendor | sponsor
    name: str
    first_seen: date | None = None
    last_seen: date | None = None
    snapshot_id: str = ""


@dataclass(frozen=True)
class Engagement:
    """A revenue or spend relationship over one period."""

    counterparty_id: str
    period_start: date
    period_end: date
    amount: float
    currency: str = "USD"
    snapshot_id: str = ""


@dataclass(frozen=True)
class Invoice:
    id: str
    counterparty_id: str
    issued: date
    due: date | None
    paid: date | None
    amount: float
    status: str = "open"           # open | paid | void
    currency: str = "USD"
    snapshot_id: str = ""

    @property
    def days_outstanding(self) -> int | None:
        """Days from issue to payment, or None while still unpaid."""
        return (self.paid - self.issued).days if self.paid else None


@dataclass(frozen=True)
class PurchaseOrder:
    id: str
    vendor_id: str
    ordered_at: date
    promised_at: date | None
    received_at: date | None
    amount: float
    line_count: int = 1
    quantity_ordered: float | None = None
    quantity_received: float | None = None
    promise_source: PromiseSource = PromiseSource.ABSENT
    currency: str = "USD"
    snapshot_id: str = ""

    @property
    def days_late(self) -> int | None:
        """Lateness against a CONTRACTED promise date only.

        Returns None when the promise date was inferred, because measuring
        lateness against our own guess would only ever prove that deliveries
        arrive roughly when they usually arrive.
        """
        if self.promise_source is not PromiseSource.CONTRACT:
            return None
        if self.promised_at is None or self.received_at is None:
            return None
        return (self.received_at - self.promised_at).days

    @property
    def lead_days(self) -> int | None:
        """Ordered to received. Available whenever both dates exist."""
        if self.received_at is None:
            return None
        return (self.received_at - self.ordered_at).days

    @property
    def short_received(self) -> bool:
        if self.quantity_ordered is None or self.quantity_received is None:
            return False
        return self.quantity_received < self.quantity_ordered * 0.98


@dataclass(frozen=True)
class CashPosition:
    as_of: date
    operating_cash: float
    # Never present in accounting data. Comes from intake or stays None; it is
    # not inferred, because a facility we invent is a safety margin we invent.
    undrawn_facility: float | None = None
    snapshot_id: str = ""


@dataclass(frozen=True)
class Expense:
    period_start: date
    period_end: date
    category: str
    amount: float
    currency: str = "USD"
    snapshot_id: str = ""


@dataclass(frozen=True)
class InventoryItem:
    sku: str
    on_hand: float
    unit_cost: float
    as_of: date
    snapshot_id: str = ""


@dataclass(frozen=True)
class Snapshot:
    """An immutable, dated read of one organisation's systems.

    A partial sync must never produce a partial simulation: either the snapshot
    is written complete or the previous snapshot stays current. `completeness`
    is what lets a later reader tell which resources were genuinely observed.
    """

    id: str
    organization_id: str
    taken_at: datetime
    source: str                                  # provider id, e.g. "fixture" | "merge"
    completeness: dict[Resource, Completeness] = field(default_factory=dict)
    record_counts: dict[Resource, int] = field(default_factory=dict)
    window_start: date | None = None             # earliest record observed
    window_end: date | None = None               # latest record observed

    def observed(self, resource: Resource) -> bool:
        """True when this resource was actually read, empty or not."""
        return self.completeness.get(resource, Completeness.ABSENT) is not Completeness.ABSENT

    @property
    def window_years(self) -> float:
        """Length of the observation window, in years.

        This is the denominator of every frequency estimate, so it is measured
        from the data rather than assumed from the sync date.
        """
        if not self.window_start or not self.window_end:
            return 0.0
        return max(0.0, (self.window_end - self.window_start).days / 365.25)


@dataclass(frozen=True)
class Book:
    """Everything one snapshot contains, in canonical form.

    The single object the estimator consumes. Engines never see it; they only
    ever see `Marginal`s, exactly as they did in v2.
    """

    organization: Organization
    snapshot: Snapshot
    counterparties: list[Counterparty] = field(default_factory=list)
    engagements: list[Engagement] = field(default_factory=list)
    invoices: list[Invoice] = field(default_factory=list)
    purchase_orders: list[PurchaseOrder] = field(default_factory=list)
    cash_positions: list[CashPosition] = field(default_factory=list)
    expenses: list[Expense] = field(default_factory=list)
    inventory: list[InventoryItem] = field(default_factory=list)

    def vendors(self) -> list[Counterparty]:
        return [c for c in self.counterparties if c.kind == "vendor"]

    def customers(self) -> list[Counterparty]:
        return [c for c in self.counterparties if c.kind == "customer"]

    def public(self) -> dict:
        """Serialised for the provenance panel and the audit trail."""
        s = self.snapshot
        return {
            "snapshot_id": s.id,
            "taken_at": s.taken_at.isoformat(),
            "source": s.source,
            "window_start": s.window_start.isoformat() if s.window_start else None,
            "window_end": s.window_end.isoformat() if s.window_end else None,
            "window_years": round(s.window_years, 2),
            "completeness": {r.value: c.value for r, c in s.completeness.items()},
            "record_counts": {r.value: n for r, n in s.record_counts.items()},
        }
