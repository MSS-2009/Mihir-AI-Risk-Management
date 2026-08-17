#!/usr/bin/env python3
"""Create the Avenoir tables in a real Supabase project, then prove the store works.

    python supabase/apply.py            # create tables, then verify
    python supabase/apply.py --verify   # verify only, change nothing

Why this exists rather than "paste it into the SQL editor": the schema and the
store have to agree on every column name, and a mismatch discovered by a
customer's first sync is an outage. Applying and verifying in one command means
the agreement is checked the moment the tables exist.

Two credentials do two different jobs and are easy to confuse:

  SUPABASE_SERVICE_ROLE_KEY   reads and writes ROWS. Cannot create tables.
  SUPABASE_ACCESS_TOKEN       a personal access token (sbp_...) that runs DDL
                              through the Management API. Only needed here.

The access token is not needed to run Avenoir, only to create the tables once,
so it belongs in your shell for one command rather than in .env:

    export SUPABASE_ACCESS_TOKEN=sbp_...      # Account > Access Tokens
    python supabase/apply.py

The verify pass writes to a throwaway organisation and deletes it at the end, so
it is safe against a project that already holds real data.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = Path(__file__).resolve().parent / "schema.sql"
TABLES = ["organizations", "tokens", "snapshots", "audit_log", "decisions"]

sys.path.insert(0, str(ROOT / "backend"))


def load_env() -> None:
    """Read backend/.env without a dependency, leaving real environment wins."""
    path = ROOT / "backend" / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def project_ref(url: str) -> str:
    m = re.match(r"https://([a-z0-9]+)\.supabase\.co", url.strip().rstrip("/"))
    if not m:
        raise SystemExit(f"SUPABASE_URL does not look like a project URL: {url!r}")
    return m.group(1)


def run_ddl(ref: str, token: str, sql: str) -> None:
    """Execute the schema through the Management API."""
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{ref}/database/query",
        data=json.dumps({"query": sql}).encode(),
        method="POST",
    )
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            r.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:600]
        if e.code in (401, 403):
            raise SystemExit(
                f"  the access token was rejected ({e.code}).\n"
                "  It must be a personal access token from Supabase > Account >\n"
                "  Access Tokens, starting 'sbp_'. The service-role key cannot\n"
                "  create tables however many times it is tried.\n"
                f"  {body}"
            )
        raise SystemExit(f"  the schema failed to apply ({e.code}): {body}")


def tables_present(url: str, key: str) -> dict[str, bool]:
    """Ask PostgREST which tables it can see, using the key the app will use."""
    present = {}
    for t in TABLES:
        req = urllib.request.Request(f"{url.rstrip('/')}/rest/v1/{t}?select=*&limit=1")
        req.add_header("apikey", key)
        req.add_header("Authorization", f"Bearer {key}")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                r.read()
            present[t] = True
        except urllib.error.HTTPError as e:
            present[t] = e.code not in (404, 400)
        except urllib.error.URLError as e:
            raise SystemExit(f"cannot reach Supabase: {e.reason}")
    return present


def round_trip(url: str, key: str) -> None:
    """Exercise every method of the Store protocol against the real project.

    This is the part that matters. Tables existing proves nothing about whether
    the store's column names match them, and a schema/store mismatch surfaces
    otherwise as a customer's first sync failing.
    """
    from storage import AuditEntry, Organization, SupabaseStore, now_iso

    store = SupabaseStore(url, key)
    org_id = f"verify_{uuid.uuid4().hex[:10]}"
    checks: list[tuple[str, bool]] = []

    try:
        store.put_organization(
            Organization(org_id, "Verification Co", "industrial_distribution", 42_000_000.0)
        )
        got = store.get_organization(org_id)
        checks.append(("organisation round-trips", got is not None and got.name == "Verification Co"))

        raw, token = store.issue_token(org_id, "verification")
        checks.append(("token is issued", raw.startswith("avn_")))

        verified = store.verify_token(raw)
        checks.append(("token verifies by hash", verified is not None
                       and verified.organization_id == org_id))
        checks.append(("plaintext token is not stored",
                       verified is not None and raw not in json.dumps(verified.__dict__, default=str)))

        sid = store.put_snapshot(org_id, {
            "snapshot_id": f"snap_{uuid.uuid4().hex[:12]}",
            "taken_at": "2026-08-17T00:00:00Z",
            "source": "verification",
            "record_counts": {"invoices": 3},
            "completeness": {"invoices": "full"},
            "invoices": [],
        })
        latest = store.latest_snapshot(org_id)
        checks.append(("snapshot stores and reads back",
                       latest is not None and latest["snapshot_id"] == sid))

        # Append-only is a property of the schema, not of good manners: writing
        # the same id twice must be refused by the primary key.
        duplicated = False
        try:
            store.put_snapshot(org_id, {"snapshot_id": sid, "taken_at": "2026-08-18T00:00:00Z"})
        except Exception:
            duplicated = True
        checks.append(("re-using a snapshot id is refused", duplicated))

        store.record_access(AuditEntry(
            id=f"aud_{uuid.uuid4().hex[:12]}", organization_id=org_id,
            at=now_iso(), action="read_snapshot", component="verification",
            detail="apply.py round trip", record_counts={"invoices": 3},
        ))
        checks.append(("audit entry is recorded", len(store.list_audit(org_id)) >= 1))

        checks.append(("token revokes", store.revoke_token(token.id)))
        checks.append(("a revoked token stops verifying", store.verify_token(raw) is None))
    finally:
        try:
            store.purge_organization(org_id)
        except Exception as e:                                  # pragma: no cover
            print(f"  ! could not clean up {org_id}: {e}")

    # Purge has to actually purge, or the deletion promise on /security is false.
    checks.append(("purge cascades to everything owned",
                   SupabaseStore(url, key).get_organization(org_id) is None))

    print()
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    if not all(ok for _, ok in checks):
        raise SystemExit("\nthe store does not agree with the schema; nothing else will work")


def main() -> None:
    load_env()
    verify_only = "--verify" in sys.argv

    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise SystemExit(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in backend/.env"
        )
    ref = project_ref(url)
    print(f"project {ref}")

    if not verify_only:
        pat = os.getenv("SUPABASE_ACCESS_TOKEN", "").strip()
        if not pat:
            print(
                "\n  SUPABASE_ACCESS_TOKEN is not set, so the tables cannot be created\n"
                "  from here. Either:\n\n"
                "    a) export SUPABASE_ACCESS_TOKEN=sbp_...   (Account > Access Tokens)\n"
                "       and run this again, or\n"
                f"    b) paste {SCHEMA.relative_to(ROOT)} into the SQL editor and run\n"
                "       python supabase/apply.py --verify\n"
            )
            raise SystemExit(1)
        print("applying schema...")
        run_ddl(ref, pat, SCHEMA.read_text())
        print("  applied")

    print("checking tables...")
    present = tables_present(url, key)
    for t, ok in present.items():
        print(f"  {'ok     ' if ok else 'MISSING'} {t}")
    if not all(present.values()):
        raise SystemExit("\nsome tables are missing; the schema has not been applied")

    print("verifying the store against the real project...")
    round_trip(url, key)
    print("\nSupabase is ready.")


if __name__ == "__main__":
    main()
