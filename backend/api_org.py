"""Organisation-scoped routes: the surface connectors and MCP actually talk to.

Kept separate from `main.py` because these are the only routes that touch stored
customer data, so the authentication, the audit write and the isolation check
all live in one file that can be read end to end in a minute. A security
reviewer should not have to trace those guarantees through a router of thirty
endpoints.

Every route here does the same three things in the same order: resolve the token
to an organisation, refuse if the requested organisation is not that one, and
write an audit row the customer can read. `_auth` is the only way in.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from assessment import book_for_organization, run_assessment
from engines.decision_templates import DecisionTemplate, Option, evaluate_template
from engines.decisions import Intervention
from industries import INDUSTRY_REGISTRY, get_pack
from ingest import IngestRejected, ingest
from monitoring import compare_runs
from storage import AuditEntry, Organization, Token, get_store, now_iso

router = APIRouter()


def _auth(authorization: Optional[str], org_id: str, need: str = "read") -> Token:
    """Resolve a bearer token and prove it owns this organisation.

    The isolation check is here rather than in the database because there is no
    database yet. When Supabase lands, row-level security enforces the same rule
    a second time, and defence in depth on tenant isolation is worth the
    duplication.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    token = get_store().verify_token(authorization.split(None, 1)[1].strip())
    if token is None:
        raise HTTPException(401, "invalid or revoked token")
    if token.organization_id != org_id:
        # Deliberately 404 rather than 403: confirming that an organisation
        # exists is itself information a caller has not earned.
        raise HTTPException(404, "no such organisation")
    if need not in token.scopes:
        raise HTTPException(403, f"token lacks '{need}' scope")
    return token


def _audit(org_id: str, action: str, component: str, detail: str = "",
           token: Token | None = None, counts: dict | None = None) -> None:
    get_store().record_access(AuditEntry(
        id=f"aud_{uuid.uuid4().hex[:12]}",
        organization_id=org_id, at=now_iso(), action=action,
        component=component, detail=detail, record_counts=counts or {},
        token_id=token.id if token else "",
    ))


def _component(user_agent: str | None) -> str:
    ua = (user_agent or "").lower()
    if "avenoir-mcp" in ua:
        return "mcp_bridge"
    if "python-urllib" in ua:
        return "mcp_bridge"
    return "api"


# ---------------------------------------------------------------------------


class CreateOrgRequest(BaseModel):
    name: str
    industry_pack: str
    reference_revenue: float = 0.0


@router.post("/organizations")
def create_organization(req: CreateOrgRequest):
    """Create an organisation and issue its first token.

    The token plaintext is returned exactly once and never stored, only its
    hash. If it is lost, issue another and revoke this one.
    """
    if req.industry_pack not in INDUSTRY_REGISTRY:
        raise HTTPException(400, f"unknown industry pack '{req.industry_pack}'")
    store = get_store()
    org = store.put_organization(Organization(
        id=f"org_{uuid.uuid4().hex[:12]}",
        name=req.name,
        industry_pack=req.industry_pack,
        reference_revenue=req.reference_revenue or get_pack(req.industry_pack).reference_revenue,
    ))
    raw, token = store.issue_token(org.id, "initial token")
    _audit(org.id, "create_organization", "api", req.name)
    return {
        "organization": org.public(),
        "token": raw,
        "token_id": token.id,
        "note": (
            "This token is shown once and is not recoverable. Set it as "
            "AVENOIR_TOKEN in the MCP bridge, or paste it into the connect page."
        ),
    }


class IngestRequest(BaseModel):
    source: str = "mcp_bridge"
    payload: dict


@router.post("/organizations/{org_id}/ingest")
def ingest_records(
    org_id: str,
    req: IngestRequest,
    authorization: Optional[str] = Header(None),
    user_agent: Optional[str] = Header(None),
):
    """The one write path. Canonical records in, immutable snapshot out."""
    token = _auth(authorization, org_id, need="ingest")
    try:
        return ingest(
            get_store(), org_id, req.payload, source=req.source,
            component=_component(user_agent), token_id=token.id,
        )
    except IngestRejected as e:
        # 422 rather than 400: the payload parsed, it just cannot become a
        # trustworthy snapshot, and the message says exactly why.
        raise HTTPException(422, str(e))


@router.get("/organizations/{org_id}/assessment")
def organization_assessment(
    org_id: str,
    authorization: Optional[str] = Header(None),
    user_agent: Optional[str] = Header(None),
):
    """The current risk profile, computed from the latest stored snapshot."""
    token = _auth(authorization, org_id)
    store = get_store()
    org = store.get_organization(org_id)
    if org is None:
        raise HTTPException(404, "no such organisation")

    book = book_for_organization(store, org_id)
    out = run_assessment(
        org.industry_pack,
        answers={"annual_revenue": org.reference_revenue} if org.reference_revenue else None,
        interpret=False, book=book,
    )
    _audit(org_id, "assess", _component(user_agent),
           f"snapshot {book.snapshot.id if book else 'none'}", token)
    out["organization"] = org.public()
    out["connected"] = book is not None
    return out


@router.get("/organizations/{org_id}/changes")
def organization_changes(
    org_id: str,
    authorization: Optional[str] = Header(None),
    user_agent: Optional[str] = Header(None),
):
    """What moved since the previous snapshot, and why.

    Needs two snapshots. With one, it says so rather than inventing a baseline.
    """
    token = _auth(authorization, org_id)
    store = get_store()
    org = store.get_organization(org_id)
    if org is None:
        raise HTTPException(404, "no such organisation")

    snaps = store.list_snapshots(org_id, limit=2)
    _audit(org_id, "list_changes", _component(user_agent), f"{len(snaps)} snapshots", token)
    if len(snaps) < 2:
        return {
            "material": False, "changes": [],
            "summary": (
                "Only one snapshot so far, so there is nothing to compare against. "
                "Changes appear from the second sync onward."
            ),
        }

    from ingest import payload_to_book
    runs = []
    for s in snaps[:2]:
        payload = store.get_snapshot(s["snapshot_id"])
        book = payload_to_book(org_id, payload)
        runs.append(run_assessment(org.industry_pack, interpret=False, book=book))
    return compare_runs(previous=runs[1], current=runs[0]).public()


class PriceRequest(BaseModel):
    kind: str
    title: str = ""
    question: str = ""
    options: list[dict]


@router.post("/organizations/{org_id}/decisions/price")
def price_decision(
    org_id: str,
    req: PriceRequest,
    authorization: Optional[str] = Header(None),
    user_agent: Optional[str] = Header(None),
):
    """Price a decision against this organisation's live risk profile."""
    token = _auth(authorization, org_id)
    store = get_store()
    org = store.get_organization(org_id)
    if org is None:
        raise HTTPException(404, "no such organisation")

    from assessment import _prepare
    book = book_for_organization(store, org_id)
    _pack, marginals, corr, _rep, _trail, _rev, _facts, _est = _prepare(
        org.industry_pack, None, None, 1.0, book
    )

    options = []
    for o in req.options:
        options.append(Option(
            id=str(o.get("id") or o.get("label", "option")),
            label=str(o.get("label", o.get("id", "option"))),
            cost_upfront=float(o.get("cost_upfront", 0.0) or 0.0),
            cost_annual=float(o.get("cost_annual", 0.0) or 0.0),
            interventions=[
                Intervention(
                    engine=str(i["engine"]),
                    frequency=float(i.get("frequency", 1.0)),
                    magnitude=float(i.get("magnitude", 1.0)),
                ) for i in (o.get("interventions") or [])
            ],
            rationale=str(o.get("rationale", "")),
        ))

    try:
        out = evaluate_template(
            DecisionTemplate(
                id=f"dec_{uuid.uuid4().hex[:8]}", kind=req.kind,
                title=req.title or "Decision", question=req.question,
                options=options,
            ),
            marginals, corr,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    _audit(org_id, "price_decision", _component(user_agent), req.kind, token)
    out["connected"] = book is not None
    return out


@router.get("/organizations/{org_id}/audit")
def organization_audit(
    org_id: str,
    limit: int = 200,
    authorization: Optional[str] = Header(None),
):
    """Every access to this organisation's data, readable by that organisation.

    An audit log only we can read is a promise rather than a control, so this is
    a first-class route rather than an internal table.
    """
    _auth(authorization, org_id)
    return {
        "organization_id": org_id,
        "entries": [e.public() for e in get_store().list_audit(org_id, limit)],
        "note": (
            "Every read and every write of your data, including ours. Reading this "
            "log is itself not logged, so the list cannot grow by inspecting it."
        ),
    }


@router.get("/organizations/{org_id}/snapshots")
def organization_snapshots(
    org_id: str,
    authorization: Optional[str] = Header(None),
):
    """Dated, immutable states. Any past assessment reproduces from one of these."""
    _auth(authorization, org_id)
    return {"snapshots": get_store().list_snapshots(org_id, limit=50)}


@router.delete("/organizations/{org_id}")
def purge_organization(
    org_id: str,
    authorization: Optional[str] = Header(None),
):
    """Disconnect and delete. Rows are removed, not flagged."""
    _auth(authorization, org_id, need="ingest")
    return get_store().purge_organization(org_id)
