"""Supabase-backed store. The same protocol `FileStore` implements.

Nothing above `storage/` changes when this is selected: the ingress endpoint,
the MCP bridge and the monitoring loop were all built and tested against the
protocol rather than against a stub, which is what makes this a drop-in rather
than a migration.

Deliberately over PostgREST with the standard library instead of the `supabase`
package. The backend already talks HTTP to two services this way, the surface
used here is five verbs, and a dependency that pulls its own HTTP stack into a
container that must stay small is a poor trade for syntax sugar.

The service-role key is used, which BYPASSES row-level security. That is
intentional and it is why the isolation check lives in `api_org._auth()` as
well: the policies in supabase/schema.sql are the second layer and the thing
that makes direct browser access safe later, not today's enforcement.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict

from .base import (
    AuditEntry,
    Organization,
    Store,
    Token,
    hash_token,
    new_token,
    now_iso,
)


class SupabaseError(RuntimeError):
    """A failed call to PostgREST, with the response body kept.

    Kept verbatim rather than summarised: PostgREST error bodies name the
    constraint or the missing relation, which is the difference between a
    two-minute fix and an afternoon.
    """


class SupabaseStore(Store):
    def __init__(self, url: str, service_role_key: str, timeout: int = 30):
        if not url or not service_role_key:
            raise ValueError("SupabaseStore needs a URL and a service-role key")
        self.base = url.rstrip("/") + "/rest/v1"
        self.key = service_role_key
        self.timeout = timeout

    # -- transport ----------------------------------------------------------

    def _request(self, method: str, path: str, body=None, prefer: str | None = None):
        url = f"{self.base}{path}"
        data = json.dumps(body, default=str).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("apikey", self.key)
        req.add_header("Authorization", f"Bearer {self.key}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        if prefer:
            req.add_header("Prefer", prefer)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read().decode()
                return json.loads(raw) if raw.strip() else None
        except urllib.error.HTTPError as e:
            raise SupabaseError(f"{method} {path} -> {e.code}: {e.read().decode()[:400]}")
        except urllib.error.URLError as e:
            raise SupabaseError(f"cannot reach Supabase: {e.reason}")

    def _select(self, table: str, query: str) -> list[dict]:
        return self._request("GET", f"/{table}?{query}") or []

    def _upsert(self, table: str, row: dict) -> None:
        self._request("POST", f"/{table}", row,
                      prefer="resolution=merge-duplicates,return=minimal")

    def _insert(self, table: str, row: dict) -> None:
        self._request("POST", f"/{table}", row, prefer="return=minimal")

    # -- organisations ------------------------------------------------------

    def put_organization(self, org: Organization) -> Organization:
        self._upsert("organizations", asdict(org))
        return org

    def get_organization(self, org_id: str) -> Organization | None:
        rows = self._select("organizations", f"id=eq.{urllib.parse.quote(org_id)}&select=*")
        return Organization(**rows[0]) if rows else None

    def list_organizations(self) -> list[Organization]:
        return [Organization(**r) for r in self._select("organizations", "select=*")]

    # -- tokens -------------------------------------------------------------

    def issue_token(self, org_id: str, label: str, scopes: list[str] | None = None):
        import uuid

        raw, digest = new_token()
        token = Token(
            id=f"tok_{uuid.uuid4().hex[:12]}",
            organization_id=org_id,
            token_hash=digest,
            label=label,
            scopes=scopes or ["read", "ingest"],
        )
        self._insert("tokens", asdict(token))
        return raw, token

    def verify_token(self, raw: str) -> Token | None:
        """Resolve a plaintext token by matching its hash.

        The lookup is by hash, so a plaintext token is never sent to the
        database and never appears in a query log.
        """
        if not raw:
            return None
        digest = hash_token(raw)
        rows = self._select(
            "tokens",
            f"token_hash=eq.{urllib.parse.quote(digest)}&revoked_at=is.null&select=*",
        )
        if not rows:
            return None
        row = rows[0]
        try:
            self._request("PATCH", f"/tokens?id=eq.{urllib.parse.quote(row['id'])}",
                          {"last_used_at": now_iso()}, prefer="return=minimal")
        except SupabaseError:
            # Last-used is a convenience for a customer auditing live
            # integrations. Failing to record it must never fail the request it
            # was recording.
            pass
        return Token(**row)

    def revoke_token(self, token_id: str) -> bool:
        rows = self._select("tokens", f"id=eq.{urllib.parse.quote(token_id)}&revoked_at=is.null&select=id")
        if not rows:
            return False
        self._request("PATCH", f"/tokens?id=eq.{urllib.parse.quote(token_id)}",
                      {"revoked_at": now_iso()}, prefer="return=minimal")
        return True

    def list_tokens(self, org_id: str) -> list[Token]:
        rows = self._select("tokens", f"organization_id=eq.{urllib.parse.quote(org_id)}&select=*")
        return [Token(**r) for r in rows]

    # -- snapshots ----------------------------------------------------------

    def put_snapshot(self, org_id: str, payload: dict) -> str:
        import uuid

        snapshot_id = payload.get("snapshot_id") or f"snap_{uuid.uuid4().hex[:16]}"
        stored = {**payload, "snapshot_id": snapshot_id,
                  "organization_id": org_id, "stored_at": now_iso()}
        # Append-only: `_insert`, never `_upsert`. Re-sending an existing
        # snapshot id must fail on the primary key rather than silently rewrite
        # history a past assessment depends on.
        self._insert("snapshots", {
            "snapshot_id": snapshot_id,
            "organization_id": org_id,
            "taken_at": stored.get("taken_at"),
            "stored_at": stored["stored_at"],
            "source": stored.get("source", ""),
            "window_start": stored.get("window_start"),
            "window_end": stored.get("window_end"),
            "record_counts": stored.get("record_counts", {}),
            "completeness": stored.get("completeness", {}),
            "payload": stored,
        })
        return snapshot_id

    def get_snapshot(self, snapshot_id: str) -> dict | None:
        rows = self._select(
            "snapshots", f"snapshot_id=eq.{urllib.parse.quote(snapshot_id)}&select=payload")
        return rows[0]["payload"] if rows else None

    def latest_snapshot(self, org_id: str) -> dict | None:
        rows = self._select(
            "snapshots",
            f"organization_id=eq.{urllib.parse.quote(org_id)}"
            "&select=payload&order=stored_at.desc&limit=1",
        )
        return rows[0]["payload"] if rows else None

    def list_snapshots(self, org_id: str, limit: int = 20) -> list[dict]:
        return self._select(
            "snapshots",
            f"organization_id=eq.{urllib.parse.quote(org_id)}"
            "&select=snapshot_id,organization_id,taken_at,stored_at,source,record_counts"
            f"&order=stored_at.desc&limit={int(limit)}",
        )

    # -- audit --------------------------------------------------------------

    def record_access(self, entry: AuditEntry) -> None:
        self._insert("audit_log", asdict(entry))

    def list_audit(self, org_id: str, limit: int = 200) -> list[AuditEntry]:
        rows = self._select(
            "audit_log",
            f"organization_id=eq.{urllib.parse.quote(org_id)}"
            f"&select=*&order=at.desc&limit={int(limit)}",
        )
        return [AuditEntry(**r) for r in rows]

    # -- revocation ---------------------------------------------------------

    def purge_organization(self, org_id: str) -> dict:
        """Delete the organisation; the schema cascades to everything it owns.

        One statement rather than five, so there is no partial state where the
        snapshots are gone and the tokens still authenticate.
        """
        snaps = self.list_snapshots(org_id, limit=1000)
        self._request("DELETE", f"/organizations?id=eq.{urllib.parse.quote(org_id)}",
                      prefer="return=minimal")
        return {
            "organization_id": org_id,
            "snapshots_deleted": len(snaps),
            "purged_at": now_iso(),
        }
