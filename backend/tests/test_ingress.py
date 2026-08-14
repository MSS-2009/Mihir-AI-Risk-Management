"""v3 ingress: storage, tokens, the push door, and organisation isolation.

The security-relevant behaviour is tested here rather than asserted in prose,
because these are the guarantees a technical evaluator will actually probe.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from connectors import FixtureProvider  # noqa: E402
from ingest import IngestRejected, book_to_payload, ingest, parse_book  # noqa: E402
from storage import FileStore, Organization  # noqa: E402


@pytest.fixture
def store():
    return FileStore(tempfile.mkdtemp())


@pytest.fixture
def org(store):
    return store.put_organization(Organization(
        "org_t", "Test Co", "industrial_distribution", 120_000_000))


def _payload():
    return book_to_payload(FixtureProvider(profile="midmarket").build())


# -- tokens -----------------------------------------------------------------

def test_tokens_are_stored_hashed_never_in_plaintext(store, org):
    raw, token = store.issue_token(org.id, "mcp bridge")
    assert raw.startswith("avn_")
    assert token.token_hash != raw
    assert raw not in token.token_hash
    assert "token_hash" not in token.public(), "an audit view must not leak the credential"


def test_a_revoked_token_stops_working(store, org):
    raw, token = store.issue_token(org.id, "bridge")
    assert store.verify_token(raw) is not None
    assert store.revoke_token(token.id)
    assert store.verify_token(raw) is None


def test_an_unknown_token_resolves_to_nothing(store):
    assert store.verify_token("avn_not_a_real_token") is None
    assert store.verify_token("") is None


# -- ingress ----------------------------------------------------------------

def test_a_pushed_book_becomes_a_readable_snapshot(store, org):
    raw, token = store.issue_token(org.id, "bridge")
    out = ingest(store, org.id, _payload(), "netsuite_onprem", "mcp_bridge", token.id)

    assert out["snapshot_id"]
    assert out["window_years"] == pytest.approx(3.0, abs=0.05)
    assert out["record_counts"]["purchase_orders"] > 0
    assert store.latest_snapshot(org.id)["snapshot_id"] == out["snapshot_id"]


def test_the_payload_survives_json(store, org):
    """The bridge sends this over the wire, so dates must already be strings."""
    import json
    json.dumps(_payload())


def test_a_promise_date_without_a_source_is_refused():
    """Lateness measured against a date we inferred is circular: it can only
    prove that deliveries arrive when they usually arrive."""
    payload = _payload()
    payload["purchase_orders"][0].pop("promise_source")
    with pytest.raises(IngestRejected, match="promise_source"):
        parse_book("org_t", payload, "test")


def test_a_resource_declared_full_but_empty_is_refused():
    """That shape reads downstream as 'we looked and nothing went wrong'."""
    payload = _payload()
    payload["purchase_orders"] = []
    with pytest.raises(IngestRejected, match="declared full"):
        parse_book("org_t", payload, "test")


def test_a_payload_with_no_dates_is_refused():
    """The window is the denominator of every frequency estimate."""
    with pytest.raises(IngestRejected, match="observation window"):
        parse_book("org_t", {"completeness": {}}, "test")


def test_the_window_comes_from_the_records_not_the_sync_date():
    book = parse_book("org_t", _payload(), "test")
    assert book.snapshot.window_start < book.snapshot.window_end
    assert book.snapshot.window_years == pytest.approx(3.0, abs=0.05)


# -- snapshots are immutable -------------------------------------------------

def test_snapshots_are_append_only(store, org):
    a = ingest(store, org.id, _payload(), "s1", "mcp_bridge")
    p2 = _payload()
    p2["snapshot_id"] = "snap_second"
    b = ingest(store, org.id, p2, "s2", "mcp_bridge")

    assert a["snapshot_id"] != b["snapshot_id"]
    assert len(store.list_snapshots(org.id)) == 2
    assert store.get_snapshot(a["snapshot_id"]) is not None, "the older state survives"
    assert not hasattr(store, "update_snapshot"), "there must be no mutation path"


def test_a_past_assessment_reproduces_from_its_snapshot(store, org):
    from assessment import run_assessment
    from ingest import payload_to_book

    ingest(store, org.id, _payload(), "s1", "mcp_bridge")
    payload = store.latest_snapshot(org.id)
    a = run_assessment("industrial_distribution", book=payload_to_book(org.id, payload),
                       interpret=False)
    b = run_assessment("industrial_distribution", book=payload_to_book(org.id, payload),
                       interpret=False)
    assert a["expected_annual_loss"] == b["expected_annual_loss"]


# -- audit and revocation ----------------------------------------------------

def test_every_ingest_is_logged(store, org):
    raw, token = store.issue_token(org.id, "bridge")
    ingest(store, org.id, _payload(), "netsuite_onprem", "mcp_bridge", token.id)
    entries = store.list_audit(org.id)
    assert entries and entries[0].action == "ingest"
    assert entries[0].component == "mcp_bridge"
    assert entries[0].token_id == token.id
    assert entries[0].record_counts


def test_purge_actually_deletes(store, org):
    """A retention promise that leaves rows in place with a deleted flag is not
    a retention promise, and it is the first thing an evaluator checks."""
    raw, token = store.issue_token(org.id, "bridge")
    ingest(store, org.id, _payload(), "s1", "mcp_bridge", token.id)

    result = store.purge_organization(org.id)
    assert result["snapshots_deleted"] == 1
    assert store.latest_snapshot(org.id) is None
    assert store.get_organization(org.id) is None
    assert store.list_tokens(org.id) == []
    assert store.list_audit(org.id) == []
    assert store.verify_token(raw) is None, "the token dies with the organisation"


# -- API isolation -----------------------------------------------------------

def test_the_api_refuses_another_organisations_data(store):
    from fastapi.testclient import TestClient

    import storage
    storage.set_store(store)
    import main

    client = TestClient(main.app)
    a = client.post("/organizations", json={
        "name": "A", "industry_pack": "industrial_distribution"}).json()
    b = client.post("/organizations", json={
        "name": "B", "industry_pack": "wealth_management"}).json()

    a_headers = {"Authorization": f"Bearer {a['token']}"}
    # A's token must not reach B, and the refusal must not confirm B exists.
    r = client.get(f"/organizations/{b['organization']['id']}/assessment", headers=a_headers)
    assert r.status_code == 404

    assert client.get(f"/organizations/{a['organization']['id']}/assessment").status_code == 401
    assert client.get(
        f"/organizations/{a['organization']['id']}/assessment",
        headers={"Authorization": "Bearer avn_wrong"},
    ).status_code == 401


def test_an_unconnected_organisation_still_assesses(store):
    """No snapshot means the v2 answer, not an error."""
    from fastapi.testclient import TestClient

    import storage
    storage.set_store(store)
    import main

    client = TestClient(main.app)
    org = client.post("/organizations", json={
        "name": "Fresh", "industry_pack": "industrial_distribution"}).json()
    r = client.get(f"/organizations/{org['organization']['id']}/assessment",
                   headers={"Authorization": f"Bearer {org['token']}"})
    assert r.status_code == 200
    assert r.json()["connected"] is False
    assert r.json()["expected_annual_loss"] > 0
