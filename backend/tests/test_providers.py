"""The Supabase store and the Merge provider, against their protocols.

The Merge mapping is tested without a live key by stubbing the transport. That
is the right level: the HTTP is four lines and Merge's own tests cover it, while
the mapping decisions, what a connection can honestly evidence, are ours and are
where a wrong answer becomes a wrong number on a customer's dashboard.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from canonical import Completeness, PromiseSource, Resource  # noqa: E402
from connectors import ConnectorProvider, MergeProvider, SyncIncomplete  # noqa: E402
from storage import FileStore, Store, SupabaseStore  # noqa: E402


# ---------------------------------------------------------------------------
# Supabase store
# ---------------------------------------------------------------------------

def test_supabase_store_satisfies_the_same_protocol_as_files():
    assert isinstance(SupabaseStore("https://x.supabase.co", "key"), Store)
    assert isinstance(FileStore("/tmp/avenoir-test-store"), Store)


def test_supabase_store_refuses_to_start_without_credentials():
    with pytest.raises(ValueError):
        SupabaseStore("", "")
    with pytest.raises(ValueError):
        SupabaseStore("https://x.supabase.co", "")


def test_it_looks_tokens_up_by_hash_never_by_plaintext(monkeypatch):
    """A plaintext token must never reach the database or a query log."""
    store = SupabaseStore("https://x.supabase.co", "key")
    seen = {}

    def fake(method, path, body=None, prefer=None):
        seen["path"] = path
        return []

    monkeypatch.setattr(store, "_request", fake)
    store.verify_token("avn_super_secret_value")
    assert "avn_super_secret_value" not in seen["path"]
    assert "token_hash=eq." in seen["path"]


def test_snapshots_are_inserted_never_upserted(monkeypatch):
    """Append-only. Re-sending an existing id must collide on the primary key
    rather than silently rewrite history a past assessment depends on."""
    store = SupabaseStore("https://x.supabase.co", "key")
    prefers = []

    def fake(method, path, body=None, prefer=None):
        prefers.append(prefer or "")
        return None

    monkeypatch.setattr(store, "_request", fake)
    store.put_snapshot("org1", {"snapshot_id": "snap1", "record_counts": {}})
    assert all("merge-duplicates" not in p for p in prefers), "snapshots must not upsert"


def test_the_two_stores_agree_on_behaviour():
    """The protocol is only worth having if both implementations mean the same
    thing, so the file store's contract is asserted here as the reference."""
    import tempfile

    store = FileStore(tempfile.mkdtemp())
    from storage import Organization

    store.put_organization(Organization("o1", "A", "industrial_distribution", 1.0))
    raw, token = store.issue_token("o1", "t")

    assert store.verify_token(raw).organization_id == "o1"
    assert store.get_organization("o1").name == "A"
    assert store.latest_snapshot("o1") is None
    sid = store.put_snapshot("o1", {"snapshot_id": "s1", "taken_at": "2026-01-01"})
    assert store.latest_snapshot("o1")["snapshot_id"] == sid
    assert store.revoke_token(token.id) and store.verify_token(raw) is None


# ---------------------------------------------------------------------------
# Merge provider
# ---------------------------------------------------------------------------

def test_merge_satisfies_the_provider_protocol():
    assert isinstance(MergeProvider(api_key="k"), ConnectorProvider)


def test_merge_has_no_write_method():
    """Read-only by construction, not by policy. There must be nothing to call."""
    p = MergeProvider(api_key="k")
    for banned in ("create", "update", "write", "post", "delete", "patch"):
        assert not any(
            attr.startswith(banned) for attr in dir(p) if not attr.startswith("_")
        ), f"a '{banned}' method would break the read-only guarantee"


ACCOUNT_DETAILS = {"id": "acc1", "integration": "QuickBooks Online",
                   "end_user_organization_name": "Demo Supply Co"}

CONTACTS = [
    {"id": "c1", "name": "Acme Customer", "is_supplier": False},
    {"id": "v1", "name": "Jiangsu Works", "is_supplier": True},
]
INVOICES = [
    {"id": "i1", "contact": "c1", "issue_date": "2025-01-15T00:00:00Z",
     "due_date": "2025-02-14T00:00:00Z", "paid_on_date": "2025-02-10T00:00:00Z",
     "total_amount": 120000, "type": "ACCOUNTS_RECEIVABLE", "currency": "USD"},
    # payable: money going OUT, must never be counted as revenue
    {"id": "i2", "contact": "v1", "issue_date": "2025-03-01T00:00:00Z",
     "total_amount": 90000, "type": "ACCOUNTS_PAYABLE", "currency": "USD"},
]
EXPENSES = [{"id": "e1", "transaction_date": "2025-02-01T00:00:00Z",
             "total_amount": 44000, "account": "cost_of_goods"}]
ACCOUNTS = [{"id": "a1", "account_type": "BANK", "current_balance": 2_400_000}]


def _stub(provider, *, purchase_orders, integration="QuickBooks Online", items=None):
    """Replace the transport, keeping every mapping decision under test."""
    pages = {
        "/contacts": CONTACTS,
        "/invoices": INVOICES,
        "/purchase-orders": purchase_orders,
        "/expenses": EXPENSES,
        "/accounts": ACCOUNTS,
        "/items": items or [],
    }

    def fake_get(path, token, params=None):
        if path == "/account-details":
            return {**ACCOUNT_DETAILS, "integration": integration}
        return {"results": pages.get(path, []), "next": None}

    provider._get = fake_get
    provider._paginate = lambda path, token, params=None: pages.get(path, [])
    return provider


def test_a_payable_invoice_is_never_counted_as_revenue():
    """Counting the vendor ledger as revenue would invent a customer book."""
    p = _stub(MergeProvider(api_key="k"), purchase_orders=[])
    book = p.fetch("token", "acc1")
    assert [i.id for i in book.invoices] == ["i1"]
    assert sum(e.amount for e in book.engagements) == 120000


def test_a_connection_without_promise_dates_says_so():
    """The failure this file exists to prevent: a missing promise date read as
    a commitment that was met."""
    pos = [{"id": "p1", "vendor": "v1", "issue_date": "2025-01-05T00:00:00Z",
            "total_amount": 50000}]                       # no delivery_date
    book = _stub(MergeProvider(api_key="k"), purchase_orders=pos).fetch("token", "acc1")

    assert book.purchase_orders[0].promise_source is PromiseSource.ABSENT
    assert book.purchase_orders[0].days_late is None
    assert book.snapshot.completeness[Resource.PURCHASE_ORDERS] is Completeness.PARTIAL


def test_a_rich_integration_that_never_fills_the_field_is_downgraded():
    """NetSuite supports promise dates; this customer does not use them. The
    capability has to follow the records, not the integration's brochure."""
    pos = [{"id": "p1", "vendor": "v1", "issue_date": "2025-01-05T00:00:00Z",
            "total_amount": 50000}]
    book = _stub(MergeProvider(api_key="k"), purchase_orders=pos,
                 integration="NetSuite").fetch("token", "acc1")
    assert book.snapshot.completeness[Resource.PURCHASE_ORDERS] is Completeness.PARTIAL


def test_a_promise_date_is_marked_as_contracted_when_present():
    pos = [{"id": "p1", "vendor": "v1", "issue_date": "2025-01-05T00:00:00Z",
            "delivery_date": "2025-02-05T00:00:00Z", "total_amount": 50000}]
    book = _stub(MergeProvider(api_key="k"), purchase_orders=pos,
                 integration="NetSuite").fetch("token", "acc1")
    po = book.purchase_orders[0]
    assert po.promise_source is PromiseSource.CONTRACT
    assert po.promised_at is not None
    # Merge has no "actually received" field, so receipt stays unset rather than
    # being assumed equal to the promise, which would report every delivery as
    # exactly on time.
    assert po.received_at is None
    assert po.days_late is None


def test_inventory_is_absent_when_no_items_come_back():
    book = _stub(MergeProvider(api_key="k"), purchase_orders=[],
                 integration="NetSuite", items=[]).fetch("token", "acc1")
    assert book.snapshot.completeness[Resource.INVENTORY] is Completeness.ABSENT


def test_undrawn_facility_is_never_invented():
    book = _stub(MergeProvider(api_key="k"), purchase_orders=[]).fetch("token", "acc1")
    assert book.cash_positions
    assert all(c.undrawn_facility is None for c in book.cash_positions)


def test_the_window_comes_from_the_records():
    pos = [{"id": "p1", "vendor": "v1", "issue_date": "2024-06-01T00:00:00Z",
            "total_amount": 1000}]
    book = _stub(MergeProvider(api_key="k"), purchase_orders=pos).fetch("token", "acc1")
    assert book.snapshot.window_start.isoformat() == "2024-06-01"
    assert book.snapshot.window_years > 0.5


def test_no_account_token_is_refused_rather_than_returning_an_empty_book():
    """An empty book would sync as 'nothing went wrong'."""
    with pytest.raises(SyncIncomplete, match="Merge Link"):
        MergeProvider(api_key="k").fetch("", "acc1")


def test_a_book_with_no_dated_records_is_refused():
    p = MergeProvider(api_key="k")
    p._get = lambda path, token, params=None: {**ACCOUNT_DETAILS, "integration": "x"}
    p._paginate = lambda path, token, params=None: []
    with pytest.raises(SyncIncomplete, match="observation window"):
        p.fetch("token", "acc1")


def test_a_merge_book_flows_through_the_estimator():
    """The whole point of the canonical boundary: the estimator cannot tell a
    Merge book from a fixture one."""
    from estimation import estimate_marginals
    from industries import get_pack

    pos = [{"id": f"p{i}", "vendor": "v1", "issue_date": "2024-06-01T00:00:00Z",
            "delivery_date": "2024-07-01T00:00:00Z", "total_amount": 1000}
           for i in range(20)]
    book = _stub(MergeProvider(api_key="k"), purchase_orders=pos,
                 integration="NetSuite").fetch("token", "acc1")

    result = estimate_marginals(get_pack("industrial_distribution").marginals(), book)
    assert result.estimates, "a Merge book must produce provenance like any other"
    assert result.coverage["total"] > 0
