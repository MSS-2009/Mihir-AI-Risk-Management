#!/usr/bin/env python3
"""Every credential Avenoir uses, what it is for, and whether it actually works.

    python scripts/preflight.py            # check what is configured locally
    python scripts/preflight.py --deploy   # also print the Render/Vercel checklist

Each credential is checked by *using* it, not by looking at its shape. A key
that is present and malformed and a key that is absent produce the same broken
app, and only one of them is visible in a listing.

The distinction this script exists to make plain: a credential in backend/.env
affects your laptop and nothing else. That file is gitignored, so it is never
uploaded to Render or Vercel. Production reads the values typed into each
platform's own dashboard, which is why something can work locally and still be
broken for everyone else. `--deploy` prints exactly which keys belong where.
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

OK, WARN, BAD = "ok  ", "note", "FAIL"


def load_env() -> None:
    path = ROOT / "backend" / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def anthropic() -> tuple[str, str]:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return WARN, "not set. Document extraction falls back to keyword matching."
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/models?limit=1",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
    )
    try:
        urllib.request.urlopen(req, timeout=20).read()
        return OK, f"authenticated ({os.getenv('ANTHROPIC_MODEL', 'default model')})"
    except urllib.error.HTTPError as e:
        return BAD, f"rejected ({e.code}). Extraction will silently degrade."
    except urllib.error.URLError as e:
        return WARN, f"unreachable: {e.reason}"


def supabase() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not (url and key):
        return WARN, "not set. Using the local file store (fine for a demo)."

    # The two Supabase keys are trivially swappable and the failure is quiet:
    # the publishable key authenticates and then returns nothing, which reads as
    # an empty database rather than as a wrong credential.
    if key.startswith("sb_publishable_") or key.startswith("eyJ"):
        if "service_role" not in key:
            return BAD, ("this looks like the anon/publishable key, not the "
                         "service-role key. It will connect and read nothing.")
    try:
        req = urllib.request.Request(f"{url.rstrip('/')}/rest/v1/organizations?select=id&limit=1",
                                     headers={"apikey": key, "Authorization": f"Bearer {key}"})
        urllib.request.urlopen(req, timeout=20).read()
        return OK, "connected, tables present"
    except urllib.error.HTTPError as e:
        if e.code in (404, 400):
            return BAD, "connected, but the tables do not exist. Run: python supabase/apply.py"
        return BAD, f"rejected ({e.code})"
    except urllib.error.URLError as e:
        return BAD, f"unreachable: {e.reason}"


def supabase_admin() -> tuple[str, str]:
    if os.getenv("SUPABASE_ACCESS_TOKEN", "").strip():
        return OK, "set. Admin only: used by supabase/apply.py, never at runtime."
    return WARN, "not set. Only needed to create tables (python supabase/apply.py)."


def merge() -> tuple[str, str]:
    from connectors import MergeProvider

    out = MergeProvider().preflight()
    if out["ok"]:
        return OK, out["detail"]
    return (WARN if out["reason"] == "no_key" else BAD), out["detail"]


CHECKS = [
    ("ANTHROPIC_API_KEY", "document extraction", anthropic),
    ("SUPABASE_*", "persistence and audit log", supabase),
    ("SUPABASE_ACCESS_TOKEN", "creating tables (admin)", supabase_admin),
    ("MERGE_API_KEY", "live accounting connectors", merge),
]

DEPLOY = """
Where each credential has to be set
-----------------------------------
backend/.env is gitignored. It is never uploaded, so nothing in it reaches
production. These are three separate places and setting one does not set another.

  Render (backend)  Dashboard > avenoir-api > Environment
      ANTHROPIC_API_KEY           required for document extraction
      SUPABASE_URL                required, or snapshots die on every deploy
      SUPABASE_SERVICE_ROLE_KEY   required, server-side only
      MERGE_API_KEY               only once a real connector exists
      MERGE_ENVIRONMENT           sandbox until then

      Not SUPABASE_ACCESS_TOKEN. It creates and drops tables and the web
      service has no reason to do either.

  Vercel (frontend)  Project > Settings > Environment Variables
      NEXT_PUBLIC_API_URL         the Render URL. Committed in
                                  frontend/.env.production, so it is already
                                  correct unless the backend URL changes.

      Anything prefixed NEXT_PUBLIC_ is compiled into the JavaScript the browser
      downloads. Never put a service-role key or an API key behind that prefix.

  Your laptop  backend/.env
      All of the above, plus SUPABASE_ACCESS_TOKEN.

After changing anything on Render, redeploy: env vars are read at boot.
"""


def main() -> None:
    load_env()
    print()
    for name, purpose, check in CHECKS:
        try:
            status, detail = check()
        except Exception as e:                                   # pragma: no cover
            status, detail = BAD, f"check itself failed: {e}"
        print(f"  [{status}] {name:24s} {purpose}")
        print(f"         {detail}\n")

    if "--deploy" in sys.argv:
        print(DEPLOY)
    else:
        print("  Run with --deploy for where each of these belongs in production.\n")


if __name__ == "__main__":
    main()
