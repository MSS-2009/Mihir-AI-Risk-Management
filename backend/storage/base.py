"""Where organisations, tokens, snapshots and the audit log live.

v2 was stateless: every number existed inside one request and vanished with it.
A connector product cannot work that way, because data arrives out of band, on a
schedule or pushed from a customer's own machine, and an assessment has to read
what arrived rather than what was posted to it.

This is the seam. One protocol, a file-backed implementation today and a
Supabase implementation when the project exists, and nothing above this layer
knows which is underneath.

Three rules the interface itself enforces:

Snapshots are immutable. There is a `put_snapshot` and no `update_snapshot`, so
a correction arrives as a new dated record and any past assessment stays exactly
reproducible from the snapshot it ran against.

Tokens are stored hashed. `verify_token` takes the plaintext and compares a
hash, so the store never holds a value that could be replayed against us.

Every read of customer data is logged. `record_access` is not optional, and the
audit log is readable by the customer whose data it describes rather than only
by us.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

TOKEN_PREFIX = "avn_"


def new_token() -> tuple[str, str]:
    """(plaintext, hash). The plaintext is shown once and never stored."""
    raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Organization:
    id: str
    name: str
    industry_pack: str
    reference_revenue: float
    created_at: str = field(default_factory=now_iso)

    def public(self) -> dict:
        return {
            "id": self.id, "name": self.name,
            "industry_pack": self.industry_pack,
            "reference_revenue": self.reference_revenue,
            "created_at": self.created_at,
        }


@dataclass
class Token:
    """A scoped credential for one organisation.

    `scopes` is deliberately explicit and read-heavy. `ingest` is the only scope
    that writes anything, and it writes only new snapshots.
    """

    id: str
    organization_id: str
    token_hash: str
    label: str
    scopes: list[str] = field(default_factory=lambda: ["read", "ingest"])
    created_at: str = field(default_factory=now_iso)
    last_used_at: str | None = None
    revoked_at: str | None = None

    @property
    def active(self) -> bool:
        return self.revoked_at is None

    def public(self) -> dict:
        """Never includes the hash: an audit view must not leak the credential."""
        return {
            "id": self.id, "organization_id": self.organization_id,
            "label": self.label, "scopes": self.scopes,
            "created_at": self.created_at, "last_used_at": self.last_used_at,
            "revoked_at": self.revoked_at, "active": self.active,
        }


@dataclass
class AuditEntry:
    """One access to customer data, visible to that customer."""

    id: str
    organization_id: str
    at: str
    action: str                 # ingest | read_snapshot | assess | list_alerts ...
    component: str              # mcp_bridge | merge_sync | dashboard | api
    detail: str = ""
    record_counts: dict = field(default_factory=dict)
    token_id: str = ""

    def public(self) -> dict:
        return {
            "id": self.id, "at": self.at, "action": self.action,
            "component": self.component, "detail": self.detail,
            "record_counts": self.record_counts, "token_id": self.token_id,
        }


@runtime_checkable
class Store(Protocol):
    """Persistence for everything a connected organisation owns."""

    # -- organisations --
    def put_organization(self, org: Organization) -> Organization: ...
    def get_organization(self, org_id: str) -> Organization | None: ...
    def list_organizations(self) -> list[Organization]: ...

    # -- tokens --
    def issue_token(self, org_id: str, label: str, scopes: list[str] | None = None) -> tuple[str, Token]:
        """Returns (plaintext, record). The plaintext is never stored."""
        ...

    def verify_token(self, raw: str) -> Token | None:
        """Resolve a plaintext token to an active record, or None."""
        ...

    def revoke_token(self, token_id: str) -> bool: ...
    def list_tokens(self, org_id: str) -> list[Token]: ...

    # -- snapshots (append-only) --
    def put_snapshot(self, org_id: str, payload: dict) -> str:
        """Write a new immutable snapshot. Returns its id."""
        ...

    def latest_snapshot(self, org_id: str) -> dict | None: ...
    def get_snapshot(self, snapshot_id: str) -> dict | None: ...
    def list_snapshots(self, org_id: str, limit: int = 20) -> list[dict]: ...

    # -- audit --
    def record_access(self, entry: AuditEntry) -> None: ...
    def list_audit(self, org_id: str, limit: int = 200) -> list[AuditEntry]: ...

    # -- revocation --
    def purge_organization(self, org_id: str) -> dict:
        """Disconnect and delete. Rows are removed, not flagged."""
        ...
