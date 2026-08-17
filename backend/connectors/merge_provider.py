"""Merge: one integration reaching QuickBooks, Xero, NetSuite, Intacct, Dynamics.

Two credentials, and which party holds each is the whole security story. WE hold
one API key for every customer. THEY authenticate through Merge Link, Merge's
own hosted flow, and we store the account token it returns. No password of
theirs ever reaches Avenoir, which is what makes the claim on /security true
rather than aspirational.

The interesting work here is not the HTTP. It is deciding what a connection can
honestly evidence.

A QuickBooks connection returns purchase orders without a vendor promise date.
The naive mapping treats a missing `delivery_date` as "no commitment was
missed", which reads downstream as a supply chain with no late deliveries: a
flattering number the customer did not earn. So capabilities are probed from the
integration itself and declared per resource, and a purchase order only carries
`PromiseSource.CONTRACT` when the field is genuinely present.

Merge normalises field NAMES across systems. It does not, and cannot, normalise
what a system actually records. That gap is this file's job.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
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
    Organization,
    PromiseSource,
    PurchaseOrder,
    Resource,
    Snapshot,
)

from .base import LinkedAccount, ProviderCapabilities, SyncIncomplete

MERGE_BASE = "https://api.merge.dev/api/accounting/v1"
PAGE_SIZE = 100
MAX_PAGES = 60          # a hard stop, so one bad cursor cannot loop forever

# Integrations known to carry vendor promise dates on purchase orders. Used only
# as a prior: the actual capability is confirmed from the records that arrive,
# because an integration supporting a field says nothing about whether this
# particular customer populates it.
PROMISE_DATE_INTEGRATIONS = {"netsuite", "sage intacct", "microsoft dynamics 365 business central"}


def _d(v) -> date | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(str(v)[:10])
        except ValueError:
            return None


def _f(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


@dataclass
class MergeProvider:
    """Read-only Merge client. No write method exists on this class."""

    api_key: str = field(default_factory=lambda: os.getenv("MERGE_API_KEY", ""))
    timeout: int = 60
    id: str = "merge"

    # -- transport ----------------------------------------------------------

    def _get(self, path: str, account_token: str, params: dict | None = None) -> dict:
        qs = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
        url = f"{MERGE_BASE}{path}" + (f"?{qs}" if qs else "")
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {self.api_key}")
        if account_token:
            req.add_header("X-Account-Token", account_token)
        req.add_header("Accept", "application/json")
        # Merge sits behind Cloudflare, which rejects requests with no
        # User-Agent as bot traffic (error 1010) before Merge ever sees them.
        req.add_header("User-Agent", "avenoir/3.0 (+https://avenoir.app)")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300]
            if e.code in (401, 403):
                raise SyncIncomplete(
                    f"Merge rejected the credentials ({e.code}): {body}. Check "
                    "MERGE_API_KEY, and that the account token belongs to it."
                )
            raise SyncIncomplete(f"Merge {path} returned {e.code}: {body}")
        except urllib.error.URLError as e:
            raise SyncIncomplete(f"cannot reach Merge: {e.reason}")

    def _paginate(self, path: str, account_token: str, params: dict | None = None) -> list[dict]:
        """Every page, or raise.

        A partial read must never become a snapshot: half the purchase orders
        reads as half the late deliveries. `SyncIncomplete` leaves the previous
        snapshot current, which is the honest outcome.
        """
        out: list[dict] = []
        cursor, pages = None, 0
        while pages < MAX_PAGES:
            page = self._get(path, account_token, {**(params or {}),
                                                   "page_size": PAGE_SIZE, "cursor": cursor})
            out.extend(page.get("results") or [])
            cursor = page.get("next")
            pages += 1
            if not cursor:
                return out
        raise SyncIncomplete(
            f"{path} exceeded {MAX_PAGES} pages; refusing to write a truncated snapshot"
        )

    # -- provider protocol --------------------------------------------------

    def authorise(self, organization_id: str, **kw) -> str:
        """Merge Link runs in the customer's browser and returns a public token
        that we exchange for an account token. There is nothing to do
        server-side before that, so this returns the Link entry point."""
        return f"{MERGE_BASE}/link-token?organization={urllib.parse.quote(organization_id)}"

    def exchange(self, public_token: str) -> str:
        """Public token to account token, once, after the customer finishes Link."""
        data = self._get(f"/link-token/{urllib.parse.quote(public_token)}", "")
        token = data.get("account_token")
        if not token:
            raise SyncIncomplete("Merge did not return an account token")
        return token

    def list_accounts(self, connection_ref: str) -> list[LinkedAccount]:
        page = self._get("/linked-accounts", "")
        out = []
        for a in page.get("results") or []:
            integration = (a.get("integration") or {}).get("name", "") or a.get("integration_name", "")
            out.append(LinkedAccount(
                id=a.get("id", ""),
                name=a.get("end_user_organization_name", "") or integration,
                system=integration.lower(),
                capabilities=self._capabilities_for(integration.lower()),
            ))
        return out

    def capabilities(self, account_id: str) -> ProviderCapabilities:
        for a in self.list_accounts(""):
            if a.id == account_id:
                return a.capabilities
        return self._capabilities_for("")

    def _capabilities_for(self, integration: str) -> ProviderCapabilities:
        """A prior, refined later by what the records actually contain."""
        rich = any(k in integration for k in PROMISE_DATE_INTEGRATIONS)
        return ProviderCapabilities(
            provider="merge",
            label=integration or "accounting system",
            supports={
                Resource.ACCOUNTS: Completeness.FULL,
                Resource.COUNTERPARTIES: Completeness.FULL,
                Resource.INVOICES: Completeness.FULL,
                Resource.EXPENSES: Completeness.FULL,
                Resource.CASH_POSITIONS: Completeness.FULL,
                Resource.PURCHASE_ORDERS: Completeness.FULL if rich else Completeness.PARTIAL,
                Resource.INVENTORY: Completeness.FULL if rich else Completeness.ABSENT,
            },
            notes={} if rich else {
                Resource.PURCHASE_ORDERS: (
                    f"{integration or 'This system'} does not usually record a vendor "
                    "promise date, so a late delivery cannot be told apart from a long "
                    "lead time."
                ),
                Resource.INVENTORY: f"{integration or 'This system'} does not track inventory levels.",
            },
        )

    # -- the sync -----------------------------------------------------------

    def fetch(self, connection_ref: str, account_id: str = "", since: date | None = None) -> Book:
        """One complete read, mapped into the canonical model.

        `connection_ref` is the account token. `since` makes the sync
        incremental by modified date; the resulting book is still complete
        because unchanged records are already in the previous snapshot.
        """
        token = connection_ref
        if not token:
            raise SyncIncomplete("no account token: the customer has not completed Merge Link")

        modified = {"modified_after": since.isoformat()} if since else {}
        info = self._get("/account-details", token)
        integration = (info.get("integration") or "").lower()
        caps = self._capabilities_for(integration)

        contacts = self._paginate("/contacts", token, modified)
        invoices_raw = self._paginate("/invoices", token, modified)
        pos_raw = self._paginate("/purchase-orders", token, modified)
        expenses_raw = self._paginate("/expenses", token, modified)
        accounts_raw = self._paginate("/accounts", token, {})
        items_raw = self._paginate("/items", token, {}) if caps.can_supply(Resource.INVENTORY) else []

        snapshot_id = f"merge_{account_id or info.get('id', 'account')}_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"

        counterparties = [
            Counterparty(
                id=str(c.get("id")),
                kind="vendor" if c.get("is_supplier") else "customer",
                name=c.get("name") or "",
                snapshot_id=snapshot_id,
            )
            for c in contacts if c.get("id")
        ]

        invoices, engagements = [], []
        for inv in invoices_raw:
            issued = _d(inv.get("issue_date"))
            if not issued or not inv.get("contact"):
                continue
            amount = _f(inv.get("total_amount"))
            # Merge distinguishes ACCOUNTS_RECEIVABLE from ACCOUNTS_PAYABLE;
            # only receivable invoices are revenue, and counting payable ones as
            # revenue would invent a customer book out of the vendor ledger.
            if str(inv.get("type", "")).upper() != "ACCOUNTS_PAYABLE":
                invoices.append(Invoice(
                    id=str(inv.get("id")), counterparty_id=str(inv.get("contact")),
                    issued=issued, due=_d(inv.get("due_date")), paid=_d(inv.get("paid_on_date")),
                    amount=amount,
                    status="paid" if inv.get("paid_on_date") else "open",
                    currency=inv.get("currency") or "USD", snapshot_id=snapshot_id,
                ))
                engagements.append(Engagement(
                    counterparty_id=str(inv.get("contact")),
                    period_start=issued, period_end=issued,
                    amount=amount, currency=inv.get("currency") or "USD",
                    snapshot_id=snapshot_id,
                ))

        purchase_orders = []
        promise_dates_seen = 0
        for po in pos_raw:
            ordered = _d(po.get("issue_date"))
            if not ordered or not po.get("vendor"):
                continue
            promised = _d(po.get("delivery_date"))
            if promised:
                promise_dates_seen += 1
            purchase_orders.append(PurchaseOrder(
                id=str(po.get("id")), vendor_id=str(po.get("vendor")),
                ordered_at=ordered, promised_at=promised,
                # Merge has no "actually received" field; the delivery date is
                # the commitment. Receipt is left unset rather than assumed to
                # equal it, because assuming it would report every delivery
                # as exactly on time.
                received_at=None,
                amount=_f(po.get("total_amount")),
                line_count=len(po.get("line_items") or []) or 1,
                promise_source=PromiseSource.CONTRACT if promised else PromiseSource.ABSENT,
                currency=po.get("currency") or "USD", snapshot_id=snapshot_id,
            ))

        expenses = []
        for e in expenses_raw:
            when = _d(e.get("transaction_date"))
            if not when:
                continue
            expenses.append(Expense(
                period_start=when, period_end=when,
                category=str((e.get("account") or "operating")),
                amount=_f(e.get("total_amount")),
                currency=e.get("currency") or "USD", snapshot_id=snapshot_id,
            ))

        # Cash is the sum of bank-type accounts as of now. Undrawn facility is
        # never in accounting data and is left None rather than invented.
        cash_total = sum(
            _f(a.get("current_balance"))
            for a in accounts_raw
            if str(a.get("account_type", "")).upper() in ("BANK", "CURRENT_ASSET", "ASSET")
        )
        cash = [CashPosition(as_of=datetime.now(timezone.utc).date(),
                             operating_cash=cash_total, undrawn_facility=None,
                             snapshot_id=snapshot_id)] if accounts_raw else []

        inventory = [
            InventoryItem(sku=str(i.get("name") or i.get("id")),
                          on_hand=_f(i.get("quantity_on_hand")),
                          unit_cost=_f(i.get("purchase_price")),
                          as_of=datetime.now(timezone.utc).date(), snapshot_id=snapshot_id)
            for i in items_raw
        ]

        # Refine the capability prior with what actually arrived. An integration
        # that supports promise dates but whose customer never fills them in is,
        # for our purposes, a connection without promise dates.
        supports = dict(caps.supports)
        notes = dict(caps.notes)
        if purchase_orders and promise_dates_seen == 0:
            supports[Resource.PURCHASE_ORDERS] = Completeness.PARTIAL
            notes[Resource.PURCHASE_ORDERS] = (
                f"{len(purchase_orders)} purchase orders arrived and none carried a "
                "vendor promise date, so lateness cannot be measured against a "
                "commitment."
            )
        if not items_raw:
            supports[Resource.INVENTORY] = Completeness.ABSENT
        caps = ProviderCapabilities(caps.provider, caps.label, supports, notes)

        dates = ([i.issued for i in invoices] + [p.ordered_at for p in purchase_orders]
                 + [e.period_start for e in expenses])
        dates = [d for d in dates if d]
        if not dates:
            raise SyncIncomplete(
                "no dated records returned; an observation window cannot be established"
            )

        counts = {
            Resource.COUNTERPARTIES: len(counterparties),
            Resource.INVOICES: len(invoices),
            Resource.PURCHASE_ORDERS: len(purchase_orders),
            Resource.EXPENSES: len(expenses),
            Resource.CASH_POSITIONS: len(cash),
            Resource.INVENTORY: len(inventory),
            Resource.ACCOUNTS: len(accounts_raw),
        }
        snapshot = Snapshot(
            id=snapshot_id, organization_id=account_id or "",
            taken_at=datetime.now(timezone.utc), source=f"merge:{integration or 'accounting'}",
            completeness={r: caps.completeness(r) for r in Resource},
            record_counts=counts, window_start=min(dates), window_end=max(dates),
        )
        return Book(
            organization=Organization(
                id=account_id or "", name=info.get("end_user_organization_name", "") or "",
                industry_pack="industrial_distribution", reference_revenue=0.0,
            ),
            snapshot=snapshot, counterparties=counterparties, engagements=engagements,
            invoices=invoices, purchase_orders=purchase_orders, cash_positions=cash,
            expenses=expenses, inventory=inventory,
        )
