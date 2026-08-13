"""The connector contract. One protocol, any accounting or ERP system.

Two rules hold this together, and both are enforced by tests rather than by
good intentions.

Engines never see a vendor's field names. Everything crosses into the canonical
model at the connector boundary, so a second provider is a mapping plus a
capability declaration and never an engine change.

A provider must declare what it *cannot* supply. This is the part that is easy
to skip and expensive to skip. A QuickBooks connection does not carry vendor
promise dates; if a provider quietly returns nothing for them, the estimator
reads zero late deliveries and reports an unusually reliable supply chain. So
capabilities are declared up front and the estimator consults them before it
draws any conclusion from an absence.

Read-only by construction. There is no write method on this protocol, so there
is no write path to disable later. That is the version of the promise that
survives a security review.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol, runtime_checkable

from canonical import Book, Completeness, Resource


@dataclass(frozen=True)
class ProviderCapabilities:
    """What one connection can actually supply, per resource.

    Keyed by resource so a single provider can report different capabilities
    per linked account: the same Merge integration reaches both NetSuite, which
    carries purchase order promise dates, and QuickBooks, which does not.
    """

    provider: str
    label: str
    supports: dict[Resource, Completeness] = field(default_factory=dict)
    # Human-readable reasons, surfaced in the provenance panel so a customer
    # sees why a parameter is still on our published estimate.
    notes: dict[Resource, str] = field(default_factory=dict)

    def completeness(self, resource: Resource) -> Completeness:
        return self.supports.get(resource, Completeness.ABSENT)

    def can_supply(self, resource: Resource) -> bool:
        return self.completeness(resource) is not Completeness.ABSENT

    def missing(self) -> list[Resource]:
        return [r for r in Resource if not self.can_supply(r)]

    def public(self) -> dict:
        return {
            "provider": self.provider,
            "label": self.label,
            "supports": {r.value: self.completeness(r).value for r in Resource},
            "notes": {r.value: n for r, n in self.notes.items()},
        }


@dataclass(frozen=True)
class LinkedAccount:
    """One customer system reachable through a provider."""

    id: str
    name: str
    system: str                      # "quickbooks" | "netsuite" | "fixture-sme" ...
    capabilities: ProviderCapabilities


@runtime_checkable
class ConnectorProvider(Protocol):
    """Read-only access to one customer's financial systems.

    Deliberately four methods. Anything more and a provider starts carrying
    behaviour that belongs in the estimator.
    """

    id: str

    def authorise(self, organization_id: str, **kw) -> str:
        """Begin a link. Returns a reference, never a credential.

        Tokens live with the aggregator. Avenoir stores a reference and nothing
        that could be replayed against a customer's system.
        """
        ...

    def list_accounts(self, connection_ref: str) -> list[LinkedAccount]:
        """The systems this connection reaches, with their capabilities."""
        ...

    def fetch(
        self,
        connection_ref: str,
        account_id: str,
        since: date | None = None,
    ) -> Book:
        """Read a complete book. Incremental by modified-date cursor via `since`.

        Returns a whole `Book` rather than a stream because a partial sync must
        never produce a partial simulation. A provider that cannot complete
        raises; the caller keeps the previous snapshot.
        """
        ...

    def capabilities(self, account_id: str) -> ProviderCapabilities:
        """What this account can supply, without fetching anything."""
        ...


class SyncIncomplete(RuntimeError):
    """Raised when a fetch cannot be completed.

    Deliberately fatal. The alternative is a snapshot that is silently missing a
    quarter of its purchase orders, which reads downstream as a quarter with no
    late deliveries. Failing keeps the previous snapshot current, which is the
    honest outcome.
    """
