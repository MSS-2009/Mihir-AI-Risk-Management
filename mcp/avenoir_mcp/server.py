"""The Avenoir MCP server: read our numbers, and push your systems to us.

One installable artifact doing two jobs, because they share an identity, a
transport and a trust boundary and splitting them would mean installing two
things that both need the same token.

READ tools make Avenoir infrastructure. A finance team's agent can ask "what is
our P95" or "price second-sourcing this component" and get a seeded, auditable
number back rather than a language model's guess. This is the direction that
matters commercially: once a customer's own agents depend on us for risk
figures, we are not a website they remember to visit.

INGRESS tools reach what Merge cannot. An aggregator covers hosted accounting
systems; it does not cover the on-premise ERP, the SQL warehouse behind a
firewall, or the folder of CSV extracts that a controller actually maintains.
This server runs inside the customer's network and pushes canonical records
OUTBOUND, so there is no inbound rule to open and no credential of theirs for us
to hold.

Implemented directly against the MCP stdio protocol rather than through an SDK,
so it has no dependency beyond the standard library and can be tested by piping
JSON at it. That matters for something a customer is asked to run inside their
own network: a small, readable, dependency-free file is a far easier thing to
get approved than a package tree.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "avenoir"
SERVER_VERSION = "3.0.0"

API_URL = os.getenv("AVENOIR_API_URL", "https://avenoir-api.onrender.com").rstrip("/")
TOKEN = os.getenv("AVENOIR_TOKEN", "")
ORG_ID = os.getenv("AVENOIR_ORG_ID", "")


# ---------------------------------------------------------------------------
# Transport to the Avenoir API
# ---------------------------------------------------------------------------

def _call(path: str, payload: dict | None = None, method: str = "POST") -> dict:
    """One request to Avenoir, with the organisation token attached."""
    url = f"{API_URL}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:400]
        raise RuntimeError(f"Avenoir returned {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot reach Avenoir at {API_URL}: {e.reason}")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "get_risk_profile",
        "description": (
            "The organisation's current quantified risk: expected annual loss, the "
            "percentile curve to plan against, which domains own the loss, and how "
            "much of it is estimated from their own history rather than published "
            "starting estimates. Every figure is a seeded simulation, reproducible "
            "from a dated snapshot."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "organization_id": {"type": "string", "description": "Defaults to AVENOIR_ORG_ID."},
            },
        },
    },
    {
        "name": "explain_parameter",
        "description": (
            "Where one parameter's value came from: measured from their data, "
            "blended, or still our published estimate, with the observation count, "
            "the window, the weight on their data, and the reason if it is not "
            "measured. Use this whenever someone asks why a number is what it is."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "engine": {"type": "string", "description": "e.g. third_party_failure"},
                "organization_id": {"type": "string"},
            },
            "required": ["engine"],
        },
    },
    {
        "name": "price_decision",
        "description": (
            "Price a business decision against the organisation's live risk profile. "
            "Returns the net present value distribution, the probability it is worth "
            "doing, AND the effect on the risk profile, which is the part a "
            "spreadsheet cannot produce. Four validated shapes only: invest_or_not, "
            "choose_between_options, act_now_or_wait, accept_or_decline_exposure."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": [
                    "invest_or_not", "choose_between_options",
                    "act_now_or_wait", "accept_or_decline_exposure",
                ]},
                "title": {"type": "string"},
                "question": {"type": "string"},
                "options": {
                    "type": "array",
                    "description": (
                        "Each option: id, label, cost_upfront, cost_annual, and "
                        "interventions [{engine, frequency, magnitude}] where the "
                        "multipliers are below 1.0 to reduce exposure."
                    ),
                    "items": {"type": "object"},
                },
                "organization_id": {"type": "string"},
            },
            "required": ["kind", "options"],
        },
    },
    {
        "name": "list_changes",
        "description": (
            "What has changed since the previous assessment and WHY. Each change "
            "states its cause, naming the parameter that moved and the observations "
            "that moved it, not merely that a number went up."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"organization_id": {"type": "string"}},
        },
    },
    {
        "name": "push_records",
        "description": (
            "Push canonical records from a local system Avenoir cannot reach: an "
            "on-premise ERP, a warehouse behind a firewall, or CSV extracts. Writes "
            "a new immutable dated snapshot. This is the ONLY tool that sends data "
            "to Avenoir, and it never reads anything it was not explicitly given. "
            "Required shape: counterparties, engagements, invoices, purchase_orders, "
            "cash_positions, expenses, inventory, plus a completeness map saying "
            "which resources this system can actually supply."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "records": {
                    "type": "object",
                    "description": "Canonical records, keyed by resource name.",
                },
                "completeness": {
                    "type": "object",
                    "description": (
                        "Per resource: 'full', 'partial' or 'absent'. Declaring a "
                        "resource full when the system cannot supply it makes an "
                        "absence look like evidence that nothing went wrong, and "
                        "Avenoir refuses payloads that do."
                    ),
                },
                "source": {"type": "string", "description": "e.g. 'netsuite_onprem'"},
                "organization_id": {"type": "string"},
            },
            "required": ["records", "completeness"],
        },
    },
    {
        "name": "read_local_csv_folder",
        "description": (
            "Read a folder of CSV extracts on THIS machine and convert them to "
            "canonical records, without sending anything. Returns what it found so a "
            "human can inspect it before calling push_records. Expects files named "
            "counterparties.csv, invoices.csv, purchase_orders.csv and so on."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string", "description": "Absolute path on this machine."},
            },
            "required": ["folder"],
        },
    },
]


def _org(args: dict) -> str:
    org = args.get("organization_id") or ORG_ID
    if not org:
        raise RuntimeError(
            "No organisation. Set AVENOIR_ORG_ID or pass organization_id."
        )
    return org


def tool_get_risk_profile(args: dict) -> dict:
    out = _call("/organizations/{}/assessment".format(_org(args)), method="GET")
    est = out.get("estimation") or {}
    cov = est.get("coverage") or {}
    curve = {p["percentile"]: p["loss"] for p in out.get("exceedance_curve", [])}
    return {
        "expected_annual_loss": out.get("expected_annual_loss"),
        "percent_of_revenue": out.get("expected_annual_loss_pct_revenue"),
        "plan_against_p95": curve.get(95),
        "plan_against_p99": curve.get(99),
        "domains": [
            {"label": d["label"], "share": d["base_share"],
             "expected_annual_loss": d["expected_annual_loss"]}
            for d in out.get("domain_contributions", [])
        ],
        "provenance": {
            "measured": cov.get("measured", 0),
            "blended": cov.get("blended", 0),
            "prior": cov.get("prior", 0),
            "total": cov.get("total", 0),
        },
        "snapshot": (est.get("snapshot") or {}).get("snapshot_id"),
        "basis": (
            "Seeded simulation over 50,000 scenarios. Parameters with no observed "
            "history remain published starting estimates, and the provenance counts "
            "above say how many."
        ),
    }


def tool_explain_parameter(args: dict) -> dict:
    engine = args["engine"]
    out = _call("/organizations/{}/assessment".format(_org(args)), method="GET")
    params = ((out.get("estimation") or {}).get("parameters")) or []
    mine = [p for p in params if p["engine"] == engine]
    if not mine:
        return {"engine": engine, "found": False,
                "note": "no such engine in this organisation's industry pack"}
    return {"engine": engine, "found": True, "parameters": mine}


def tool_price_decision(args: dict) -> dict:
    return _call("/organizations/{}/decisions/price".format(_org(args)), {
        "kind": args["kind"],
        "title": args.get("title", ""),
        "question": args.get("question", ""),
        "options": args["options"],
    })


def tool_list_changes(args: dict) -> dict:
    return _call("/organizations/{}/changes".format(_org(args)), method="GET")


def tool_push_records(args: dict) -> dict:
    payload = dict(args["records"])
    payload["completeness"] = args["completeness"]
    return _call("/organizations/{}/ingest".format(_org(args)), {
        "source": args.get("source", "mcp_bridge"),
        "payload": payload,
    })


def tool_read_local_csv_folder(args: dict) -> dict:
    """Read, convert, and return. Deliberately does not send.

    Separating reading from sending is the whole transparency story for local
    data: a human sees exactly what would leave the building before anything
    does, and the tool that reads has no ability to transmit.
    """
    import csv
    from pathlib import Path

    folder = Path(args["folder"]).expanduser()
    if not folder.is_dir():
        raise RuntimeError(f"not a folder: {folder}")

    known = [
        "counterparties", "engagements", "invoices", "purchase_orders",
        "cash_positions", "expenses", "inventory",
    ]
    records, found, missing = {}, {}, []
    for name in known:
        path = folder / f"{name}.csv"
        if not path.exists():
            missing.append(name)
            continue
        with path.open(newline="") as fh:
            rows = [dict(r) for r in csv.DictReader(fh)]
        records[name] = rows
        found[name] = len(rows)

    return {
        "folder": str(folder),
        "records": records,
        "found": found,
        "missing_files": missing,
        "suggested_completeness": {
            **{n: "full" for n in found},
            **{n: "absent" for n in missing},
        },
        "note": (
            "Nothing has been sent. Review this, correct the completeness map if a "
            "file is only a partial extract, then call push_records. A resource "
            "marked full that is really partial will make an absence look like "
            "evidence that nothing went wrong."
        ),
    }


HANDLERS = {
    "get_risk_profile": tool_get_risk_profile,
    "explain_parameter": tool_explain_parameter,
    "price_decision": tool_price_decision,
    "list_changes": tool_list_changes,
    "push_records": tool_push_records,
    "read_local_csv_folder": tool_read_local_csv_folder,
}


# ---------------------------------------------------------------------------
# MCP stdio protocol
# ---------------------------------------------------------------------------

def _result(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle(message: dict) -> dict | None:
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}

    if method == "initialize":
        return _result(request_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })

    if method in ("notifications/initialized", "initialized"):
        return None                      # notification: no reply

    if method == "tools/list":
        return _result(request_id, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        handler = HANDLERS.get(name)
        if not handler:
            return _error(request_id, -32601, f"unknown tool '{name}'")
        try:
            payload = handler(args)
            return _result(request_id, {
                "content": [{"type": "text", "text": json.dumps(payload, indent=1, default=str)}]
            })
        except Exception as e:                      # surfaced to the agent, not swallowed
            return _result(request_id, {
                "content": [{"type": "text", "text": f"Avenoir error: {e}"}],
                "isError": True,
            })

    if method == "ping":
        return _result(request_id, {})

    return _error(request_id, -32601, f"unknown method '{method}'")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        reply = handle(message)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
