#!/usr/bin/env python3
"""Export every row Avenoir holds to a local file, and restore from one.

    python supabase/backup.py                     # write a timestamped backup
    python supabase/backup.py --list              # what backups exist
    python supabase/backup.py --restore FILE      # put rows back
    python supabase/backup.py --restore FILE --dry-run

Supabase's own backups are a plan feature. On the free tier there are none at
all, so `pitr_enabled: false` and an empty backup list means a dropped table is
unrecoverable. That is an unacceptable position to be in while holding a
customer's financial records, and a paid plan is the real fix. This exists
because a backup you run yourself is the one that is not conditional on billing
state, and because a restore path that has never been executed is not a restore
path.

Restore is deliberately additive and refuses to overwrite. A restore that
clobbers is the tool most likely to destroy the data it was reached for, and it
is always reached for on the worst day of the month, by someone in a hurry.

The output holds real customer financials, so it is written to a gitignored
directory and should be treated exactly like the database.
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backend" / ".data" / "backups"
PAGE = 1000

# Order matters on restore: a row cannot reference a parent that is not there
# yet, so parents are written first and the foreign keys enforce it.
TABLES = ["organizations", "tokens", "snapshots", "audit_log", "decisions"]
KEYS = {"organizations": "id", "tokens": "id", "snapshots": "snapshot_id",
        "audit_log": "id", "decisions": "id"}

sys.path.insert(0, str(ROOT / "supabase"))
from apply import load_env  # noqa: E402


def _req(url: str, key: str, method="GET", body=None, prefer=None):
    data = json.dumps(body, default=str).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("apikey", key)
    r.add_header("Authorization", f"Bearer {key}")
    r.add_header("Content-Type", "application/json")
    r.add_header("User-Agent", "avenoir-backup/3.0")
    if prefer:
        r.add_header("Prefer", prefer)
    with urllib.request.urlopen(r, timeout=120) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw.strip() else None


def dump(url: str, key: str) -> dict:
    """Page through every table. Paging is not optional: PostgREST caps a
    response, and a backup silently truncated at the cap is worse than none,
    because it looks like a backup."""
    out: dict[str, list] = {}
    for t in TABLES:
        rows, offset = [], 0
        while True:
            page = _req(
                f"{url.rstrip('/')}/rest/v1/{t}?select=*&order={KEYS[t]}.asc"
                f"&limit={PAGE}&offset={offset}", key) or []
            rows.extend(page)
            if len(page) < PAGE:
                break
            offset += PAGE
        out[t] = rows
        print(f"  {len(rows):6d}  {t}")
    return out


def write(tables: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUT / f"avenoir-{stamp}.json.gz"
    payload = {
        "taken_at": datetime.now(timezone.utc).isoformat(),
        "project": os.getenv("SUPABASE_URL", ""),
        "row_counts": {t: len(r) for t, r in tables.items()},
        "tables": tables,
    }
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(payload, f, default=str)

    # Read it back before claiming success. A backup that was never opened is a
    # belief, not a backup, and the failure mode is finding out during a restore.
    with gzip.open(path, "rt", encoding="utf-8") as f:
        back = json.load(f)
    if back["row_counts"] != payload["row_counts"]:
        path.unlink()
        raise SystemExit("the backup did not read back correctly; it was deleted")
    return path


def restore(url: str, key: str, path: Path, dry_run: bool) -> None:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        payload = json.load(f)
    tables = payload["tables"]

    print(f"backup from {payload['taken_at']}")
    for t in TABLES:
        print(f"  {len(tables.get(t, [])):6d}  {t}")

    live = {t: len(_req(f"{url.rstrip('/')}/rest/v1/{t}?select={KEYS[t]}&limit=1", key) or [])
            for t in TABLES}
    if any(live.values()):
        print("\n  the target already holds rows. Restore only inserts rows whose")
        print("  primary key is absent; nothing existing is modified or removed.")

    if dry_run:
        print("\n--dry-run: nothing was written")
        return

    for t in TABLES:
        rows = tables.get(t) or []
        if not rows:
            continue
        inserted = skipped = 0
        for i in range(0, len(rows), 100):
            chunk = rows[i:i + 100]
            try:
                # ignore-duplicates, never merge-duplicates: an existing row is
                # newer than the backup by definition, so it wins.
                _req(f"{url.rstrip('/')}/rest/v1/{t}", key, "POST", chunk,
                     prefer="resolution=ignore-duplicates,return=minimal")
                inserted += len(chunk)
            except urllib.error.HTTPError as e:
                skipped += len(chunk)
                print(f"    {t}: a chunk was refused ({e.code}): {e.read().decode()[:160]}")
            time.sleep(0.05)
        print(f"  {t}: {inserted} sent, {skipped} refused")
    print("\nrestore complete. Run python supabase/apply.py --verify")


def main() -> None:
    load_env()
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not (url and key):
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

    if "--list" in sys.argv:
        files = sorted(OUT.glob("avenoir-*.json.gz"))
        if not files:
            raise SystemExit(f"no backups in {OUT}")
        for f in files:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                counts = json.load(fh)["row_counts"]
            print(f"  {f.name}  {sum(counts.values()):6d} rows  "
                  f"{f.stat().st_size / 1024:.0f} KB")
        return

    if "--restore" in sys.argv:
        path = Path(sys.argv[sys.argv.index("--restore") + 1])
        if not path.exists():
            raise SystemExit(f"no such backup: {path}")
        restore(url, key, path, "--dry-run" in sys.argv)
        return

    print("reading every table...")
    path = write(dump(url, key))
    print(f"\nwritten and verified: {path}")
    print(f"  {path.stat().st_size / 1024:.0f} KB. This holds real customer "
          f"financials; it is gitignored and belongs wherever the database belongs.")


if __name__ == "__main__":
    main()
