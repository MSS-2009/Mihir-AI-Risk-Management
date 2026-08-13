"""CP1: the canonical model and the fixture connector.

The point of these tests is that the fixture is trustworthy enough to build an
estimator against. If the fixture lies, everything downstream is measuring
nothing, and it would do so silently.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from canonical import Book, Completeness, PromiseSource, Resource  # noqa: E402
from connectors import (  # noqa: E402
    MIDMARKET_NETSUITE,
    SME_QUICKBOOKS,
    ConnectorProvider,
    FixtureProvider,
)


def test_fixture_satisfies_the_provider_protocol():
    assert isinstance(FixtureProvider(), ConnectorProvider)


def test_the_same_seed_builds_the_same_book():
    """Snapshots must be reproducible or 'why did the number change' has no answer."""
    a, b = FixtureProvider().build(), FixtureProvider().build()
    assert [(p.id, p.received_at, p.amount) for p in a.purchase_orders] == \
           [(p.id, p.received_at, p.amount) for p in b.purchase_orders]
    assert [(i.id, i.amount, i.paid) for i in a.invoices] == \
           [(i.id, i.amount, i.paid) for i in b.invoices]


def test_a_different_seed_builds_a_different_book():
    a, b = FixtureProvider(seed=1).build(), FixtureProvider(seed=2).build()
    assert [p.amount for p in a.purchase_orders] != [p.amount for p in b.purchase_orders]


def test_planted_late_deliveries_are_exact_and_recoverable():
    """Exact, not Poisson-drawn.

    The first version drew the count from Poisson(rate * years). On this
    generator's seed that returned zero, so the book held no late deliveries and
    a test asserting the estimator recovers the rate would have passed while
    measuring nothing at all.
    """
    p = FixtureProvider(profile="midmarket")
    book = p.build()

    assert p.truth.n_late == round(p.truth.late_delivery_rate * p.truth.years)
    observed = [po for po in book.purchase_orders
                if (po.days_late or 0) > p.truth.late_threshold_days]
    assert len(observed) == p.truth.n_late
    assert sorted(po.id for po in observed) == sorted(p.planted["late_po_ids"])


def test_planted_churn_is_unambiguous():
    """A customer who stops in the final quarter is indistinguishable from one
    whose invoice has not been raised, so planted churn stops early enough to be
    detectable without a fuzzy assertion."""
    p = FixtureProvider(profile="midmarket")
    book = p.build()
    end = book.snapshot.window_end

    last: dict[str, object] = {}
    for e in book.engagements:
        last[e.counterparty_id] = max(last.get(e.counterparty_id, e.period_end), e.period_end)
    gone = sorted(c for c, d in last.items() if (end - d).days > 200)

    assert gone == p.planted["churned_customer_ids"]
    assert len(gone) == p.truth.n_churn


def test_the_default_profile_is_the_poor_one():
    """Building against the rich profile yields an estimator that works on data
    no real customer has. The default has to be the common case."""
    assert FixtureProvider().capabilities() is SME_QUICKBOOKS
    assert SME_QUICKBOOKS.completeness(Resource.INVENTORY) is Completeness.ABSENT
    assert SME_QUICKBOOKS.completeness(Resource.PURCHASE_ORDERS) is Completeness.PARTIAL
    assert SME_QUICKBOOKS.notes[Resource.PURCHASE_ORDERS]


def test_absent_is_not_the_same_as_empty():
    """The distinction the estimator depends on: a connection that cannot carry
    purchase order promise dates must not read as a supply chain with no late
    deliveries."""
    sme = FixtureProvider(profile="sme").build()
    rich = FixtureProvider(profile="midmarket").build()

    assert sme.purchase_orders, "orders exist"
    assert all(po.days_late is None for po in sme.purchase_orders), "but lateness is unmeasurable"
    assert all(po.promise_source is PromiseSource.ABSENT for po in sme.purchase_orders)
    assert any(po.days_late is not None for po in rich.purchase_orders)

    assert not sme.snapshot.observed(Resource.INVENTORY)
    assert rich.snapshot.observed(Resource.INVENTORY)


def test_lateness_is_never_measured_against_an_inferred_promise():
    """Measuring lateness against a date we inferred from typical lead time can
    only ever prove that deliveries arrive when they usually arrive."""
    from canonical import PurchaseOrder
    from datetime import date as d

    po = PurchaseOrder(
        id="x", vendor_id="v", ordered_at=d(2026, 1, 1),
        promised_at=d(2026, 2, 1), received_at=d(2026, 3, 1), amount=1000.0,
        promise_source=PromiseSource.INFERRED,
    )
    assert po.days_late is None, "inferred promise dates must not yield lateness"
    assert po.lead_days == 59, "but the raw lead time is still observable"


def test_snapshot_window_is_measured_from_the_data():
    book = FixtureProvider().build()
    assert abs(book.snapshot.window_years - FixtureProvider().truth.years) < 0.02
    assert book.snapshot.window_start < book.snapshot.window_end


def test_engines_and_industries_never_import_connectors():
    """The boundary that makes a second provider a mapping change.

    If an engine learns a vendor's field names, adding QuickBooks stops being a
    connector change and becomes a modelling change.
    """
    root = Path(__file__).resolve().parent.parent
    offenders = []
    for pkg in ("engines", "industries"):
        for path in (root / pkg).rglob("*.py"):
            src = path.read_text()
            if "import connectors" in src or "from connectors" in src or "import canonical" in src:
                offenders.append(str(path.relative_to(root)))
    assert not offenders, f"engines/industries must not import the connector layer: {offenders}"


def test_undrawn_facility_is_never_invented():
    """It is not in accounting data. Inventing it invents a safety margin."""
    book = FixtureProvider(profile="midmarket").build()
    assert book.cash_positions
    assert all(c.undrawn_facility is None for c in book.cash_positions)
