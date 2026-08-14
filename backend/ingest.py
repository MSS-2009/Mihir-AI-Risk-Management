"""Canonical records in, immutable snapshot out. The one door data comes through.

The architectural point of this file: **the canonical `Book` is already the
ingress contract**, so nothing downstream needs to know how records arrived.
Merge pulls them server-side, the MCP bridge pushes them from inside a
customer's network, a fixture generates them, and the estimator cannot tell the
difference. That is why connectors and MCP did not require a second calculation
system, and why a third source later will not either.

Push rather than pull for anything outside Merge. A bridge running on the
customer's machine sends records outbound to this endpoint, so there is no
inbound firewall rule, no VPN, and no credential of theirs held by us. That is
the version of the integration story that survives a security review, and it is
the only model that reaches an on-premise system at all.

Partial ingest is refused, not accepted. A snapshot missing a quarter of its
purchase orders reads downstream as a quarter with no late deliveries, which is
a flattering number the customer did not earn. Either the snapshot is written
whole or the previous one stays current.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import date, datetime, timezone

from canonical import (
    Book,
    CashPosition,
    Completeness,
    Counterparty,
    Engagement,
    Expense,
    InventoryItem,
    Invoice,
    Organization as CanonicalOrg,
    PromiseSource,
    PurchaseOrder,
    Resource,
    Snapshot,
)
from storage.base import AuditEntry, Store, now_iso


class IngestRejected(ValueError):
    """The payload cannot become a complete snapshot. Nothing is written."""


def _date(v):
    if v in (None, ""):
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    return date.fromisoformat(str(v)[:10])


def _rows(payload: dict, key: str) -> list[dict]:
    rows = payload.get(key) or []
    if not isinstance(rows, list):
        raise IngestRejected(f"'{key}' must be a list")
    return rows


def parse_book(org_id: str, payload: dict, source: str) -> Book:
    """Turn a pushed payload into a canonical Book, or refuse it.

    Validation is strict on the things the estimator will later trust and
    permissive on everything else. In particular a purchase order that claims a
    promise date must say where the date came from: measuring lateness against a
    date we inferred can only ever prove that deliveries arrive when they
    usually arrive, so `promise_source` is required rather than defaulted.
    """
    completeness = {}
    for r in Resource:
        raw = (payload.get("completeness") or {}).get(r.value, "absent")
        try:
            completeness[r] = Completeness(raw)
        except ValueError:
            raise IngestRejected(
                f"completeness for '{r.value}' must be one of "
                f"{[c.value for c in Completeness]}, got '{raw}'"
            )

    snapshot_id = payload.get("snapshot_id") or f"snap_{uuid.uuid4().hex[:16]}"

    counterparties = [
        Counterparty(
            id=str(c["id"]), kind=str(c.get("kind", "vendor")), name=str(c.get("name", "")),
            first_seen=_date(c.get("first_seen")), last_seen=_date(c.get("last_seen")),
            snapshot_id=snapshot_id,
        ) for c in _rows(payload, "counterparties")
    ]

    engagements = [
        Engagement(
            counterparty_id=str(e["counterparty_id"]),
            period_start=_date(e["period_start"]), period_end=_date(e["period_end"]),
            amount=float(e["amount"]), currency=str(e.get("currency", "USD")),
            snapshot_id=snapshot_id,
        ) for e in _rows(payload, "engagements")
    ]

    invoices = [
        Invoice(
            id=str(i["id"]), counterparty_id=str(i["counterparty_id"]),
            issued=_date(i["issued"]), due=_date(i.get("due")), paid=_date(i.get("paid")),
            amount=float(i["amount"]), status=str(i.get("status", "open")),
            currency=str(i.get("currency", "USD")), snapshot_id=snapshot_id,
        ) for i in _rows(payload, "invoices")
    ]

    purchase_orders = []
    for p in _rows(payload, "purchase_orders"):
        promised = _date(p.get("promised_at"))
        raw_source = p.get("promise_source")
        if promised is not None and not raw_source:
            raise IngestRejected(
                "a purchase order with a promised_at must state promise_source "
                "('contract' or 'inferred'); lateness measured against an inferred "
                "date is circular and will not be trusted"
            )
        try:
            psource = PromiseSource(raw_source) if raw_source else PromiseSource.ABSENT
        except ValueError:
            raise IngestRejected(
                f"promise_source must be one of {[s.value for s in PromiseSource]}"
            )
        purchase_orders.append(PurchaseOrder(
            id=str(p["id"]), vendor_id=str(p["vendor_id"]),
            ordered_at=_date(p["ordered_at"]), promised_at=promised,
            received_at=_date(p.get("received_at")), amount=float(p.get("amount", 0.0)),
            line_count=int(p.get("line_count", 1)),
            quantity_ordered=p.get("quantity_ordered"),
            quantity_received=p.get("quantity_received"),
            promise_source=psource, currency=str(p.get("currency", "USD")),
            snapshot_id=snapshot_id,
        ))

    cash = [
        CashPosition(
            as_of=_date(c["as_of"]), operating_cash=float(c["operating_cash"]),
            undrawn_facility=c.get("undrawn_facility"), snapshot_id=snapshot_id,
        ) for c in _rows(payload, "cash_positions")
    ]
    expenses = [
        Expense(
            period_start=_date(e["period_start"]), period_end=_date(e["period_end"]),
            category=str(e.get("category", "other")), amount=float(e["amount"]),
            currency=str(e.get("currency", "USD")), snapshot_id=snapshot_id,
        ) for e in _rows(payload, "expenses")
    ]
    inventory = [
        InventoryItem(
            sku=str(i["sku"]), on_hand=float(i.get("on_hand", 0.0)),
            unit_cost=float(i.get("unit_cost", 0.0)), as_of=_date(i["as_of"]),
            snapshot_id=snapshot_id,
        ) for i in _rows(payload, "inventory")
    ]

    # The observation window is measured from the records themselves, never from
    # the sync date: it is the denominator of every frequency estimate, and a
    # window we assumed would silently change every rate we report.
    dates: list[date] = []
    dates += [e.period_start for e in engagements] + [e.period_end for e in engagements]
    dates += [i.issued for i in invoices]
    dates += [p.ordered_at for p in purchase_orders]
    dates += [c.as_of for c in cash]
    dates = [d for d in dates if d]
    if not dates:
        raise IngestRejected(
            "no dated records: an observation window cannot be established, and "
            "without one no frequency can be estimated"
        )

    counts = {
        Resource.COUNTERPARTIES: len(counterparties),
        Resource.INVOICES: len(invoices),
        Resource.PURCHASE_ORDERS: len(purchase_orders),
        Resource.CASH_POSITIONS: len(cash),
        Resource.EXPENSES: len(expenses),
        Resource.INVENTORY: len(inventory),
        Resource.ACCOUNTS: 1,
    }

    # A resource declared present but delivered empty is the one contradiction
    # worth refusing: it is exactly the shape that reads downstream as "we
    # looked and found nothing wrong".
    for resource, n in counts.items():
        if completeness.get(resource) is Completeness.FULL and n == 0 and resource not in (
            Resource.ACCOUNTS, Resource.CASH_POSITIONS, Resource.EXPENSES,
        ):
            raise IngestRejected(
                f"'{resource.value}' is declared full but no records were sent. "
                "Send 'partial' or 'absent' instead: an empty full resource reads "
                "as evidence that nothing went wrong."
            )

    org = payload.get("organization") or {}
    snapshot = Snapshot(
        id=snapshot_id,
        organization_id=org_id,
        taken_at=datetime.now(timezone.utc),
        source=source,
        completeness=completeness,
        record_counts=counts,
        window_start=min(dates),
        window_end=max(dates),
    )
    return Book(
        organization=CanonicalOrg(
            id=org_id,
            name=str(org.get("name", org_id)),
            industry_pack=str(org.get("industry_pack", "industrial_distribution")),
            reference_revenue=float(org.get("reference_revenue", 0.0) or 0.0),
        ),
        snapshot=snapshot,
        counterparties=counterparties,
        engagements=engagements,
        invoices=invoices,
        purchase_orders=purchase_orders,
        cash_positions=cash,
        expenses=expenses,
        inventory=inventory,
    )


def _jsonable(row: dict) -> dict:
    """Dates to ISO strings, enums to values.

    `asdict` preserves `date` objects, which are not JSON serialisable, so a
    payload built this way would fail the moment it crossed the wire. It has to
    happen here rather than at the transport, because the same payload is both
    pushed by the bridge and written to the snapshot store.
    """
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, date):
            out[k] = v.isoformat()
        elif hasattr(v, "value") and hasattr(v, "name"):
            out[k] = v.value
        else:
            out[k] = v
    return out


def book_to_payload(book: Book) -> dict:
    """Serialise a Book for storage and for the wire. The inverse of `parse_book`."""
    return {
        "snapshot_id": book.snapshot.id,
        "taken_at": book.snapshot.taken_at.isoformat(),
        "source": book.snapshot.source,
        "window_start": book.snapshot.window_start.isoformat() if book.snapshot.window_start else None,
        "window_end": book.snapshot.window_end.isoformat() if book.snapshot.window_end else None,
        "completeness": {r.value: c.value for r, c in book.snapshot.completeness.items()},
        "record_counts": {r.value: n for r, n in book.snapshot.record_counts.items()},
        "organization": {
            "name": book.organization.name,
            "industry_pack": book.organization.industry_pack,
            "reference_revenue": book.organization.reference_revenue,
        },
        "counterparties": [_jsonable(asdict(c)) for c in book.counterparties],
        "engagements": [_jsonable(asdict(e)) for e in book.engagements],
        "invoices": [_jsonable(asdict(i)) for i in book.invoices],
        "purchase_orders": [_jsonable(asdict(p)) for p in book.purchase_orders],
        "cash_positions": [_jsonable(asdict(c)) for c in book.cash_positions],
        "expenses": [_jsonable(asdict(e)) for e in book.expenses],
        "inventory": [_jsonable(asdict(i)) for i in book.inventory],
    }


def payload_to_book(org_id: str, payload: dict) -> Book:
    """Rehydrate a stored snapshot. Reproducing a past run depends on this."""
    return parse_book(org_id, payload, payload.get("source", "stored"))


def ingest(
    store: Store,
    org_id: str,
    payload: dict,
    source: str,
    component: str,
    token_id: str = "",
) -> dict:
    """Validate, store immutably, and log. The only write path into the system."""
    book = parse_book(org_id, payload, source)
    stored = book_to_payload(book)
    snapshot_id = store.put_snapshot(org_id, stored)

    store.record_access(AuditEntry(
        id=f"aud_{uuid.uuid4().hex[:12]}",
        organization_id=org_id,
        at=now_iso(),
        action="ingest",
        component=component,
        detail=f"snapshot {snapshot_id} from {source}",
        record_counts={r.value: n for r, n in book.snapshot.record_counts.items()},
        token_id=token_id,
    ))

    return {
        "snapshot_id": snapshot_id,
        "window_start": stored["window_start"],
        "window_end": stored["window_end"],
        "window_years": round(book.snapshot.window_years, 2),
        "record_counts": stored["record_counts"],
        "completeness": stored["completeness"],
        "accepted_at": now_iso(),
    }
