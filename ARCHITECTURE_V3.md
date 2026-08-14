# Avenoir v3 architecture: connectors, MCP, and how data reaches the engines

## The inversion, stated plainly

v2 was a website that computed a number from a form. v3 is a service that lives
inside a customer's systems, watches them, and interrupts when something material
changes. That is not a feature difference, it is a different product, and it
changes what the front door is.

The single most important thing I found while building this: **v2 had no ingress
path at all.** Every endpoint was stateless request-response, customer data
existed only inside one request body, and nothing persisted. A connector product
cannot work that way, because data arrives out of band, on a schedule or pushed
from a machine we do not control, and an assessment has to read what arrived
rather than what was posted to it.

So the work was not "add connectors to the website". It was: add persistence,
identity, an ingress door, and an audit trail, then invert the navigation to
match.

---

## 1. Does the MCP service need a new system? No, and here is why

**The canonical `Book` was already the ingress contract.**

`backend/canonical.py` defines one vocabulary. Every source produces it and the
estimator cannot tell them apart:

```
Merge (pull, server-side)  ─┐
MCP bridge (push, on-prem) ─┼─►  canonical Book  ─►  estimator ─► engines
Fixture (seeded, tests)    ─┘         ▲
CSV / document upload      ───────────┘
```

That boundary is enforced by a test: no module under `engines/` or `industries/`
may import from `connectors/` or `canonical`. It means a third source later is a
mapping change, never a modelling change, and it is why MCP needed **zero**
changes to the eleven engines, the copula, the robustness layer or the packs.

What it did need, all of which is now built:

| Piece | File | Why it did not exist before |
|---|---|---|
| Persistence | `backend/storage/` | v2 never stored anything |
| Identity + scoped tokens | `backend/storage/base.py` | no organisations existed |
| Ingress door | `backend/ingest.py` | data only arrived in request bodies |
| Org-scoped API | `backend/api_org.py` | every route was global |
| Audit log | `storage.record_access` | nothing to audit when nothing persisted |
| The bridge itself | `mcp/avenoir_mcp/server.py` | new |

---

## 2. What the MCP server is, and how it interacts

One installable artifact doing two jobs, because they share an identity, a
transport and a trust boundary.

### Read tools: Avenoir becomes infrastructure

A customer's own agent asks us for numbers.

- `get_risk_profile` — expected annual loss, the percentile curve, domain shares, provenance counts
- `explain_parameter` — where one number came from, with observation count, window and weight
- `price_decision` — a decision priced against their live profile, **including its effect on the tail**
- `list_changes` — what moved since the last sync and the parameter that moved it

This is the commercially important half. Once a finance team's agent depends on
us for risk figures, we are not a site someone remembers to visit.

### Ingress tools: reach what Merge cannot

- `read_local_csv_folder` — reads local extracts, converts to canonical, **sends nothing**
- `push_records` — the only tool that transmits; writes one dated immutable snapshot

Reading and sending are deliberately separate tools. The tool that reads local
files has no ability to transmit, so a person sees exactly what would leave the
building before any of it does.

### Interaction with the existing system

```
Customer network                        │  Avenoir
                                        │
their agent ──► avenoir_mcp.server ─────┼──► POST /organizations/{id}/ingest
                (stdio, Python stdlib)  │         │
                       │                │         ▼
                       │                │    parse_book() ── refuses partial
                       │                │         │
                       │                │         ▼
                       └────────────────┼──► put_snapshot()  (append-only)
                          GET assessment│         │
                                        │         ▼
                                        │    estimator ─► engines ─► dashboard
```

No new calculation system. `run_assessment(..., book=book_for_organization(...))`
is the entire integration, and with no snapshot it returns exactly the v2 answer.

**Dependency-free on purpose.** The bridge is one stdlib-only file implementing
MCP stdio directly rather than pulling an SDK. A customer is being asked to run
this inside their network; a small readable file is a far easier thing to get
approved than a package tree, and it can be tested by piping JSON at it.

---

## 3. How connectors send information in, and the transparency

**Direction: push for anything not hosted.** Merge sync runs server-side (pull),
but the MCP bridge pushes outbound. No inbound firewall rule, no VPN, no
credential of theirs held by us. It is the only model that reaches an on-premise
ERP at all, and it is the version of the story that survives a security review.

**Authentication:** a bearer token scoped to one organisation, `read` and
`ingest` only. Stored as a SHA-256 hash, so we hold nothing replayable. Shown
once. `_auth()` in `api_org.py` is the only way in, and it returns **404, not
403**, for a mismatched organisation, because confirming an organisation exists
is information a caller has not earned.

**What is refused, and why it matters more than what is accepted:**

- A purchase order with a `promised_at` but no `promise_source` is rejected.
  Measuring lateness against a date we inferred can only prove that deliveries
  arrive when they usually arrive.
- A resource declared `full` that arrives empty is rejected. That shape reads
  downstream as "we looked and nothing went wrong", which is a flattering number
  the customer did not earn.
- A payload with no dated records is rejected. The observation window is the
  denominator of every frequency estimate, so it is measured from the records,
  never assumed from the sync date.
- Partial ingest is never written. Either the snapshot is whole or the previous
  one stays current.

**Transparency, at three depths:**

| Depth | Where | What they see |
|---|---|---|
| Access | `GET /organizations/{id}/audit` | Every read and write: when, what, which component, under which token. Reading the log is not itself logged. |
| State | `GET /organizations/{id}/snapshots` | Every dated immutable snapshot, with record counts and completeness |
| Number | Dashboard provenance panel | Per parameter: measured, blended or ours, with observations, window, weight, and the reason when it is still ours |

---

## 4. Frontend, restructured

| Route | Role | Status |
|---|---|---|
| `/` | Home | exists, hero already industry-neutral |
| `/connect` | **Connectors + MCP download.** The front door. | **built** |
| `/methodology` | How numbers are made, incl. estimation | exists, extended |
| `/pricing` | Pricing | exists |
| `/manual` | The v2 flow, moved to the back | **built** |
| `/security` | Security posture | built |
| `/dashboard`, `/intake`, `/start`, `/upload` | Retained; reached via `/manual` | existing |

Navigation now reads **Connect · Dashboard · Methodology · Pricing · Manual**.
The questionnaire is no longer the front door.

---

## 5. What is built and verified tonight

Proven end to end with a live backend and the real MCP server:

```
org created            → org_7e1879c9a96f, token issued once
bridge pushes a book   → snap_20260812_midmarket, 3.0 yrs, 378 POs
agent: get_risk_profile→ EAL $1,997,203 | P95 $3,990,261 | P99 $5,948,836
                          provenance 0 measured / 2 blended / 10 prior
agent: explain_parameter→ third_party_failure frequency, blended,
                          n=3, w=0.50, 0.4583 → 0.7294
                          magnitude: prior, "financial records show what was
                          paid, not what a disruption cost"
agent: price_decision  → NPV -$1,070 (p10 -$288,896 to p90 $389,931), 36%
                          AND cuts P95 by $334,980, P99 by $474,376
                          break-even at $94,570/yr, priced against live snapshot
auth                   → no token 401, wrong organisation 404
```

---

## 6. What remains

1. **Merge provider** — the protocol and capability declaration exist; the HTTP
   implementation needs a Merge account.
2. **Supabase** — `storage/` is file-backed behind a protocol. Supabase is one
   new file plus row-level security policies; nothing above it changes.
3. **Scheduled sync** — the monitoring loop and change detection are built and
   tested. Render cron is a separate service type at $1/month minimum, so this
   needs a decision on paying or moving to GitHub Actions.
4. **Packaging the bridge** — currently a file to run; should become
   `pip install avenoir-mcp` with a signed release.
5. **Alert delivery** — changes are computed with causes; email and Slack
   delivery are not wired.

---

## 7. Two risks worth stating

**The token model is interim.** A single bearer token per organisation, verified
in application code, is correct for design partners and not sufficient at scale.
Supabase row-level security is the second enforcement layer, and the isolation
check stays in `_auth` as defence in depth rather than being replaced.

**MCP shifts the trust boundary onto the customer's machine.** The bridge runs
where their data is, which is what makes it useful, and it also means a
compromised workstation could push fabricated records. Snapshots are immutable
and attributed to a token, so a bad push is attributable and revocable rather
than silent, but signing pushes is the real answer and is not built.
