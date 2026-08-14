"""File-backed store. Real persistence with no database to provision.

Deliberately not a stub. Everything above this layer, the ingress endpoint, the
MCP bridge, the monitoring loop, gets built and tested against real reads and
writes, so swapping in Supabase changes one file rather than discovering the
whole design assumed something a database will not do.

The trade-offs are stated rather than hidden: single process, no row-level
security, no concurrent writers. That is fine for design partners on one dyno
and is exactly what Supabase replaces.
"""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict
from pathlib import Path

from .base import (
    AuditEntry,
    Organization,
    Store,
    Token,
    hash_token,
    new_token,
    now_iso,
)

DEFAULT_ROOT = Path(__file__).resolve().parent.parent / ".data"


class FileStore(Store):
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root else DEFAULT_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "snapshots").mkdir(exist_ok=True)
        # One lock, because a partially written index is worse than a slow one.
        self._lock = threading.Lock()

    # -- helpers ------------------------------------------------------------

    def _read(self, name: str) -> list[dict]:
        p = self.root / f"{name}.json"
        return json.loads(p.read_text()) if p.exists() else []

    def _write(self, name: str, rows: list[dict]) -> None:
        (self.root / f"{name}.json").write_text(json.dumps(rows, indent=1, default=str))

    # -- organisations ------------------------------------------------------

    def put_organization(self, org: Organization) -> Organization:
        with self._lock:
            rows = [r for r in self._read("organizations") if r["id"] != org.id]
            rows.append(asdict(org))
            self._write("organizations", rows)
        return org

    def get_organization(self, org_id: str) -> Organization | None:
        for r in self._read("organizations"):
            if r["id"] == org_id:
                return Organization(**r)
        return None

    def list_organizations(self) -> list[Organization]:
        return [Organization(**r) for r in self._read("organizations")]

    # -- tokens -------------------------------------------------------------

    def issue_token(self, org_id: str, label: str, scopes: list[str] | None = None):
        raw, digest = new_token()
        token = Token(
            id=f"tok_{uuid.uuid4().hex[:12]}",
            organization_id=org_id,
            token_hash=digest,
            label=label,
            scopes=scopes or ["read", "ingest"],
        )
        with self._lock:
            rows = self._read("tokens")
            rows.append(asdict(token))
            self._write("tokens", rows)
        return raw, token

    def verify_token(self, raw: str) -> Token | None:
        if not raw:
            return None
        digest = hash_token(raw)
        rows = self._read("tokens")
        for r in rows:
            if r["token_hash"] == digest and r.get("revoked_at") is None:
                # Last-used is genuinely useful to a customer auditing which
                # integration is still live, so it is worth the write.
                with self._lock:
                    for row in rows:
                        if row["id"] == r["id"]:
                            row["last_used_at"] = now_iso()
                    self._write("tokens", rows)
                return Token(**r)
        return None

    def revoke_token(self, token_id: str) -> bool:
        with self._lock:
            rows = self._read("tokens")
            found = False
            for r in rows:
                if r["id"] == token_id and r.get("revoked_at") is None:
                    r["revoked_at"] = now_iso()
                    found = True
            self._write("tokens", rows)
        return found

    def list_tokens(self, org_id: str) -> list[Token]:
        return [Token(**r) for r in self._read("tokens") if r["organization_id"] == org_id]

    # -- snapshots ----------------------------------------------------------

    def put_snapshot(self, org_id: str, payload: dict) -> str:
        """Append-only. There is no update path, by design."""
        snapshot_id = payload.get("snapshot_id") or f"snap_{uuid.uuid4().hex[:16]}"
        payload = {**payload, "snapshot_id": snapshot_id,
                   "organization_id": org_id, "stored_at": now_iso()}
        with self._lock:
            (self.root / "snapshots" / f"{snapshot_id}.json").write_text(
                json.dumps(payload, indent=1, default=str)
            )
            index = self._read("snapshot_index")
            index.append({
                "snapshot_id": snapshot_id,
                "organization_id": org_id,
                "taken_at": payload.get("taken_at"),
                "stored_at": payload["stored_at"],
                "source": payload.get("source", ""),
                "record_counts": payload.get("record_counts", {}),
            })
            self._write("snapshot_index", index)
        return snapshot_id

    def get_snapshot(self, snapshot_id: str) -> dict | None:
        p = self.root / "snapshots" / f"{snapshot_id}.json"
        return json.loads(p.read_text()) if p.exists() else None

    def latest_snapshot(self, org_id: str) -> dict | None:
        rows = [r for r in self._read("snapshot_index") if r["organization_id"] == org_id]
        if not rows:
            return None
        newest = max(rows, key=lambda r: r["stored_at"])
        return self.get_snapshot(newest["snapshot_id"])

    def list_snapshots(self, org_id: str, limit: int = 20) -> list[dict]:
        rows = [r for r in self._read("snapshot_index") if r["organization_id"] == org_id]
        return sorted(rows, key=lambda r: r["stored_at"], reverse=True)[:limit]

    # -- audit --------------------------------------------------------------

    def record_access(self, entry: AuditEntry) -> None:
        with self._lock:
            rows = self._read("audit")
            rows.append(asdict(entry))
            self._write("audit", rows)

    def list_audit(self, org_id: str, limit: int = 200) -> list[AuditEntry]:
        rows = [r for r in self._read("audit") if r["organization_id"] == org_id]
        return [AuditEntry(**r) for r in sorted(rows, key=lambda r: r["at"], reverse=True)[:limit]]

    # -- revocation ---------------------------------------------------------

    def purge_organization(self, org_id: str) -> dict:
        """Disconnect and delete. Rows are removed, not flagged.

        A retention promise that leaves the data in place with a deleted flag is
        not a retention promise, and it is the first thing a technical evaluator
        checks.
        """
        with self._lock:
            index = self._read("snapshot_index")
            mine = [r for r in index if r["organization_id"] == org_id]
            for r in mine:
                p = self.root / "snapshots" / f"{r['snapshot_id']}.json"
                p.unlink(missing_ok=True)
            self._write("snapshot_index", [r for r in index if r["organization_id"] != org_id])

            for name, key in (("tokens", "organization_id"),
                              ("audit", "organization_id"),
                              ("organizations", "id")):
                rows = self._read(name)
                self._write(name, [r for r in rows if r.get(key) != org_id])

        return {
            "organization_id": org_id,
            "snapshots_deleted": len(mine),
            "purged_at": now_iso(),
        }
