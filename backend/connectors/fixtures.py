"""A deterministic fake customer, so the whole product runs without credentials.

Not a convenience. Three things depend on this provider being real:

Every test and the entire local loop run with no network and no secrets, which
is what keeps the estimator testable at all.

The demo runs without a live customer connection, which matters because the
first conversations happen before anyone has linked an account.

And the estimator can be tested against *planted* truth. The generator plants an
exact number of events and records which records carry them, so a test asserts
the estimator recovers something we know we put there rather than asserting that
today's output equals yesterday's. That is the difference between a regression
test and a correctness test, and only one of them catches a wrong estimator.

The default profile is deliberately the poor one. `SME_QUICKBOOKS` carries no
purchase order promise dates and no inventory, because that is what a small
distributor's QuickBooks actually looks like. Building against the rich profile
would produce an estimator that works beautifully on data no real customer has.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np

from canonical import (
    Book,
    CashPosition,
    Completeness,
    Counterparty,
    Engagement,
    Expense,
    InventoryItem,
    Invoice,
    Organization,
    PromiseSource,
    PurchaseOrder,
    Resource,
    Snapshot,
)

from .base import LinkedAccount, ProviderCapabilities

# ---------------------------------------------------------------------------
# Capability profiles. The pessimistic one is the default on purpose.
# ---------------------------------------------------------------------------

SME_QUICKBOOKS = ProviderCapabilities(
    provider="fixture",
    label="Small business, QuickBooks-grade",
    supports={
        Resource.ACCOUNTS: Completeness.FULL,
        Resource.COUNTERPARTIES: Completeness.FULL,
        Resource.INVOICES: Completeness.FULL,
        Resource.EXPENSES: Completeness.FULL,
        Resource.CASH_POSITIONS: Completeness.FULL,
        # Purchase orders exist but carry no vendor commitment date, which is
        # the common case and the one that costs us two measured frequencies.
        Resource.PURCHASE_ORDERS: Completeness.PARTIAL,
        Resource.INVENTORY: Completeness.ABSENT,
    },
    notes={
        Resource.PURCHASE_ORDERS: (
            "Purchase orders carry order and receipt dates but no vendor promise "
            "date, so lateness cannot be measured against a commitment."
        ),
        Resource.INVENTORY: "This system does not track inventory levels.",
    },
)

MIDMARKET_NETSUITE = ProviderCapabilities(
    provider="fixture",
    label="Mid-market, NetSuite-grade",
    supports={r: Completeness.FULL for r in Resource},
    notes={},
)

PROFILES = {"sme": SME_QUICKBOOKS, "midmarket": MIDMARKET_NETSUITE}


# ---------------------------------------------------------------------------
# Planted truth. Tests assert the estimator recovers these.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlantedTruth:
    """The generating parameters. A test that cannot see these is not a test.

    Event counts are planted EXACTLY, as `round(rate * years)`, rather than
    drawn from a Poisson with that rate. Drawing them looks more realistic and
    is worse: on this generator's first seed, Poisson(2.7) returned zero, so the
    book contained no late deliveries at all and any test asserting the
    estimator recovers the rate would have passed while measuring nothing.

    Sampling variability belongs in the estimator's own tests, where the
    observation count is a parameter and can be varied deliberately. A fixture's
    job is known ground truth.
    """

    late_delivery_rate: float = 0.9      # vendor failures per year
    churn_rate: float = 0.6              # customers lost per year
    price_shock_rate: float = 1.4        # material input price moves per year
    years: float = 3.0
    vendor_count: int = 14
    customer_count: int = 22
    annual_revenue: float = 120_000_000.0
    late_threshold_days: int = 14

    @property
    def n_late(self) -> int:
        return int(round(self.late_delivery_rate * self.years))

    @property
    def n_churn(self) -> int:
        return int(round(self.churn_rate * self.years))

    def public(self) -> dict:
        return {
            "late_delivery_rate": self.late_delivery_rate,
            "churn_rate": self.churn_rate,
            "price_shock_rate": self.price_shock_rate,
            "years_observed": self.years,
            "n_late_planted": self.n_late,
            "n_churn_planted": self.n_churn,
        }


@dataclass
class FixtureProvider:
    """A whole customer, generated from a seed.

    Same seed, same book, byte for byte. The determinism is load-bearing: a
    snapshot has to be reproducible or "why did the number change" has no
    answer.
    """

    seed: int = 20260812
    profile: str = "sme"
    truth: PlantedTruth = field(default_factory=PlantedTruth)
    id: str = "fixture"
    # Filled by build(). Which records actually carry the planted events, so a
    # test asserts recovery of specific rows rather than of a summary statistic.
    planted: dict = field(default_factory=dict)

    # -- provider protocol --------------------------------------------------

    def authorise(self, organization_id: str, **kw) -> str:
        """No credential exists to exchange, so the reference is a stable hash."""
        digest = hashlib.sha256(f"{organization_id}:{self.seed}".encode()).hexdigest()
        return f"fixture_conn_{digest[:16]}"

    def capabilities(self, account_id: str = "") -> ProviderCapabilities:
        return PROFILES.get(self.profile, SME_QUICKBOOKS)

    def list_accounts(self, connection_ref: str) -> list[LinkedAccount]:
        caps = self.capabilities()
        return [LinkedAccount(
            id=f"{self.profile}_account",
            name="Demo Industrial Supply",
            system=f"fixture-{self.profile}",
            capabilities=caps,
        )]

    def fetch(self, connection_ref: str, account_id: str = "", since: date | None = None) -> Book:
        return self.build()

    # -- generation ---------------------------------------------------------

    def build(self, industry_pack: str = "industrial_distribution") -> Book:
        rng = np.random.default_rng(self.seed)
        self.planted = {}
        caps = self.capabilities()
        t = self.truth

        end = date(2026, 6, 30)
        start = end - timedelta(days=int(t.years * 365.25))
        snapshot_id = f"snap_{self.seed}_{self.profile}"

        org = Organization(
            id="org_fixture",
            name="Demo Industrial Supply",
            industry_pack=industry_pack,
            reference_revenue=t.annual_revenue,
        )

        vendors = [
            Counterparty(f"v{i}", "vendor", f"Vendor {chr(65 + i)}", start, end, snapshot_id)
            for i in range(t.vendor_count)
        ]
        customers = [
            Counterparty(f"c{i}", "customer", f"Customer {i + 1}", start, end, snapshot_id)
            for i in range(t.customer_count)
        ]

        pos = self._purchase_orders(rng, vendors, start, end, caps, snapshot_id)
        invoices, engagements, churned = self._revenue(rng, customers, start, end, snapshot_id)
        expenses = self._expenses(rng, start, end, snapshot_id)
        cash = self._cash(rng, end, snapshot_id)
        inventory = (
            self._inventory(rng, end, snapshot_id)
            if caps.can_supply(Resource.INVENTORY) else []
        )

        counts = {
            Resource.COUNTERPARTIES: len(vendors) + len(customers),
            Resource.PURCHASE_ORDERS: len(pos),
            Resource.INVOICES: len(invoices),
            Resource.EXPENSES: len(expenses),
            Resource.CASH_POSITIONS: len(cash),
            Resource.INVENTORY: len(inventory),
            Resource.ACCOUNTS: 1,
        }
        snapshot = Snapshot(
            id=snapshot_id,
            organization_id=org.id,
            taken_at=datetime(2026, 6, 30, 12, 0, 0),
            source="fixture",
            completeness={r: caps.completeness(r) for r in Resource},
            record_counts=counts,
            window_start=start,
            window_end=end,
        )
        return Book(
            organization=org,
            snapshot=snapshot,
            counterparties=vendors + customers,
            engagements=engagements,
            invoices=invoices,
            purchase_orders=pos,
            cash_positions=cash,
            expenses=expenses,
            inventory=inventory,
        )

    # -- resources ----------------------------------------------------------

    def _purchase_orders(self, rng, vendors, start, end, caps, snap) -> list[PurchaseOrder]:
        """Orders across the window, with late deliveries planted at a known rate.

        The count of late deliveries is exactly `round(rate * years)`, assigned
        to randomly chosen orders. Exact rather than drawn, so a test can assert
        the estimator recovers a number we know we put there.
        """
        t = self.truth
        has_promise = caps.completeness(Resource.PURCHASE_ORDERS) is Completeness.FULL
        span = (end - start).days
        n_orders = int(t.vendor_count * t.years * 9)   # ~9 orders per vendor per year

        n_late = min(t.n_late, n_orders)
        late_idx = set(rng.choice(n_orders, size=n_late, replace=False).tolist())

        out = []
        for i in range(n_orders):
            vendor = vendors[i % len(vendors)]
            ordered = start + timedelta(days=int(rng.integers(0, max(span - 60, 1))))
            planned = int(rng.integers(18, 45))
            promised = ordered + timedelta(days=planned)
            slip = int(rng.integers(t.late_threshold_days + 1, 70)) if i in late_idx else int(rng.integers(-4, 6))
            received = promised + timedelta(days=slip)
            amount = float(np.round(rng.lognormal(mean=10.4, sigma=0.7), 2))
            qty = float(rng.integers(40, 900))
            if i in late_idx:
                self.planted.setdefault("late_po_ids", []).append(f"po{i}")
            out.append(PurchaseOrder(
                id=f"po{i}",
                vendor_id=vendor.id,
                ordered_at=ordered,
                promised_at=promised if has_promise else None,
                received_at=received,
                amount=amount,
                line_count=int(rng.integers(1, 7)),
                quantity_ordered=qty,
                quantity_received=qty if i not in late_idx else float(np.round(qty * 0.9, 2)),
                promise_source=PromiseSource.CONTRACT if has_promise else PromiseSource.ABSENT,
                snapshot_id=snap,
            ))
        return out

    def _revenue(self, rng, customers, start, end, snap):
        """Quarterly revenue per customer, with a few customers planted as churned.

        Concentration is Zipf-like, which is what a real book looks like and
        what makes counterparty concentration worth measuring at all.
        """
        t = self.truth
        n_q = max(1, int(t.years * 4))
        weights = np.array([1.0 / (i + 1) ** 0.9 for i in range(len(customers))])
        weights = weights / weights.sum()
        quarterly_total = t.annual_revenue / 4.0

        n_churn = min(t.n_churn, len(customers) - 3)
        churned = set(rng.choice(len(customers), size=n_churn,
                                 replace=False).tolist()) if n_churn else set()
        # Churned customers stop at a random quarter, so the estimator has to
        # detect the stop rather than be told about it.
        # Stop at least two quarters before the window ends. A customer who goes
        # quiet in the final quarter is indistinguishable from one whose invoice
        # has not been raised yet, and planting an ambiguous event would force
        # the test that reads it to be fuzzy.
        stop_q = {i: int(rng.integers(2, max(3, n_q - 1))) for i in churned}

        invoices, engagements = [], []
        for q in range(n_q):
            p_start = start + timedelta(days=int(q * 91.3))
            p_end = p_start + timedelta(days=91)
            for ci, cust in enumerate(customers):
                if ci in stop_q and q >= stop_q[ci]:
                    continue
                amount = float(np.round(quarterly_total * weights[ci] * rng.uniform(0.85, 1.15), 2))
                engagements.append(Engagement(cust.id, p_start, p_end, amount, snapshot_id=snap))
                issued = p_start + timedelta(days=int(rng.integers(0, 80)))
                terms = int(rng.choice([30, 45, 60]))
                paid_lag = terms + int(rng.integers(-8, 34))
                paid = issued + timedelta(days=paid_lag)
                invoices.append(Invoice(
                    id=f"inv{q}_{ci}",
                    counterparty_id=cust.id,
                    issued=issued,
                    due=issued + timedelta(days=terms),
                    paid=paid if paid <= end else None,
                    amount=amount,
                    status="paid" if paid <= end else "open",
                    snapshot_id=snap,
                ))
        self.planted["churned_customer_ids"] = sorted(customers[i].id for i in churned)
        return invoices, engagements, churned

    def _expenses(self, rng, start, end, snap) -> list[Expense]:
        t = self.truth
        cats = ["cost_of_goods", "payroll", "freight", "facilities", "software"]
        share = [0.62, 0.21, 0.07, 0.06, 0.04]
        out, months = [], max(1, int(t.years * 12))
        for m in range(months):
            p_start = start + timedelta(days=int(m * 30.4))
            for cat, s in zip(cats, share):
                amt = t.annual_revenue / 12.0 * 0.86 * s * float(rng.uniform(0.9, 1.1))
                out.append(Expense(p_start, p_start + timedelta(days=30), cat,
                                   float(np.round(amt, 2)), snapshot_id=snap))
        return out

    def _cash(self, rng, end, snap) -> list[CashPosition]:
        """Monthly cash for the last year. Undrawn facility stays None: it is not
        in accounting data and inventing it would invent a safety margin."""
        out = []
        for m in range(12):
            as_of = end - timedelta(days=int(m * 30.4))
            out.append(CashPosition(
                as_of=as_of,
                operating_cash=float(np.round(self.truth.annual_revenue * 0.055
                                              * float(rng.uniform(0.8, 1.2)), 2)),
                undrawn_facility=None,
                snapshot_id=snap,
            ))
        return sorted(out, key=lambda c: c.as_of)

    def _inventory(self, rng, end, snap) -> list[InventoryItem]:
        return [
            InventoryItem(f"SKU-{i:04d}", float(rng.integers(0, 2400)),
                          float(np.round(rng.lognormal(4.2, 0.6), 2)), end, snap)
            for i in range(60)
        ]
