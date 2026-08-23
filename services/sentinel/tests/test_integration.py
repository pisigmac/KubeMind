"""End-to-end sentinel HTTP tests.

`TestClient(app)` used bare does not run the lifespan, so `store` and `ledger`
stayed None and every endpoint answered 503. The client has to be used as a
context manager, and each test needs its own database or ingests collide on
the span_id unique constraint.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACER_DB_PATH", str(tmp_path / "spans.db"))
    monkeypatch.setenv("AUDIT_LEDGER_URL", f"sqlite:///{tmp_path}/ledger.db")
    monkeypatch.delenv("KUBEMIND_API_KEYS", raising=False)
    monkeypatch.delenv("KUBEMIND_SERVICE_KEY", raising=False)

    from sentinel.main import app

    with TestClient(app) as c:
        yield c


def _span(span_id="span-1", workspace="test", **attrs):
    return {
        "trace_id": "trace-1",
        "span_id": span_id,
        "workspace_id": workspace,
        "service": "router",
        "operation": "llm_call",
        "start_time": "2024-01-01T00:00:00",
        "status": "ok",
        "attributes": attrs or {"model": "llama3.1"},
    }


class TestHealth:
    def test_health(self, client):
        data = client.get("/health").json()
        assert data["service"] == "sentinel"

    def test_prometheus_scrape(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]


class TestSpans:
    def test_ingest_and_query(self, client):
        assert client.post("/v1/spans", json=_span()).status_code == 200

        data = client.get("/v1/spans?workspace_id=test").json()
        assert data["count"] == 1
        assert data["spans"][0]["service"] == "router"

    def test_query_by_post(self, client):
        client.post("/v1/spans", json=_span())
        data = client.post("/v1/spans/query", json={"workspace_id": "test"}).json()
        assert data["count"] == 1

    def test_metrics(self, client):
        client.post("/v1/spans", json=_span())
        data = client.get("/v1/metrics?workspace_id=test").json()
        assert data["total_spans"] == 1
        assert "services" in data

    def test_export_includes_a_checksum(self, client):
        client.post("/v1/spans", json=_span())
        data = client.get("/v1/export?workspace_id=test").json()
        assert data["count"] == 1
        assert len(data["redaction"]["checksum_sha256"]) == 64

    def test_pii_is_redacted_before_storage(self, client):
        client.post(
            "/v1/spans",
            json=_span(prompt="email me at alice@example.com"),
        )
        stored = client.get("/v1/spans?workspace_id=test").json()["spans"][0]
        assert "alice@example.com" not in str(stored["attributes"])

    def test_workspaces_are_isolated(self, client):
        client.post("/v1/spans", json=_span("a", workspace="one"))
        client.post("/v1/spans", json=_span("b", workspace="two"))
        assert client.get("/v1/spans?workspace_id=one").json()["count"] == 1


class TestAuditEndpoints:
    def test_ingest_returns_a_ledger_receipt(self, client):
        receipt = client.post("/v1/spans", json=_span()).json()["ledger"]
        assert receipt["chain_seq"] == 1
        assert len(receipt["entry_hash"]) == 64

    def test_verify_reports_an_intact_chain(self, client):
        for i in range(3):
            client.post("/v1/spans", json=_span(f"span-{i}"))
        data = client.get("/v1/audit/verify?workspace_id=test").json()
        assert data["valid"] is True
        assert data["entries_checked"] == 3

    def test_verify_detects_tampering(self, client):
        from sqlalchemy import text

        from sentinel import main

        for i in range(3):
            client.post("/v1/spans", json=_span(f"span-{i}"))
        with main.ledger.engine.begin() as conn:
            conn.execute(
                text("UPDATE audit_entries SET payload = '{}' WHERE chain_seq = 2")
            )

        data = client.get("/v1/audit/verify?workspace_id=test").json()
        assert data["valid"] is False
        assert data["broken_at"]["chain_seq"] == 2

    def test_head_advances_with_each_entry(self, client):
        client.post("/v1/spans", json=_span("a"))
        first = client.get("/v1/audit/head?workspace_id=test").json()["head_hash"]
        client.post("/v1/spans", json=_span("b"))
        second = client.get("/v1/audit/head?workspace_id=test").json()["head_hash"]
        assert first != second

    def test_entries_are_listed_newest_first(self, client):
        for i in range(3):
            client.post("/v1/spans", json=_span(f"span-{i}"))
        entries = client.get("/v1/audit/entries?workspace_id=test").json()["entries"]
        assert [e["chain_seq"] for e in entries] == [3, 2, 1]

    def test_retention_defaults_then_updates(self, client):
        assert (
            client.get("/v1/audit/retention?workspace_id=test").json()["retention_days"]
            == 90
        )
        client.post(
            "/v1/audit/retention", json={"workspace_id": "test", "retention_days": 30}
        )
        assert (
            client.get("/v1/audit/retention?workspace_id=test").json()["retention_days"]
            == 30
        )

    def test_legal_hold_round_trips(self, client):
        client.post(
            "/v1/audit/retention", json={"workspace_id": "test", "legal_hold": True}
        )
        assert (
            client.get("/v1/audit/retention?workspace_id=test").json()["legal_hold"]
            is True
        )

    def test_stats_report_the_backend(self, client):
        client.post("/v1/spans", json=_span())
        assert client.get("/v1/audit/stats").json()["backend"] == "sqlite"


class TestAuthEnforcement:
    @pytest.fixture
    def secured(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TRACER_DB_PATH", str(tmp_path / "spans.db"))
        monkeypatch.setenv("AUDIT_LEDGER_URL", f"sqlite:///{tmp_path}/ledger.db")
        monkeypatch.setenv("KUBEMIND_API_KEYS", "k-acme:acme,k-globex:globex")

        import importlib

        from sentinel import main

        importlib.reload(main)
        with TestClient(main.app) as c:
            yield c
        importlib.reload(main)

    def test_unauthenticated_read_is_refused(self, secured):
        assert secured.get("/v1/spans").status_code == 401

    def test_cross_tenant_read_is_refused(self, secured):
        # The hole this closes: `?workspace_id=` was a plain query parameter.
        resp = secured.get(
            "/v1/spans?workspace_id=globex", headers={"X-API-Key": "k-acme"}
        )
        assert resp.status_code == 403

    def test_own_workspace_read_is_allowed(self, secured):
        resp = secured.get(
            "/v1/spans?workspace_id=acme", headers={"X-API-Key": "k-acme"}
        )
        assert resp.status_code == 200

    def test_ingest_is_bound_to_the_key_not_the_body(self, secured):
        """Otherwise anyone can forge audit entries against another tenant."""
        resp = secured.post(
            "/v1/spans",
            json=_span(workspace="globex"),
            headers={"X-API-Key": "k-acme"},
        )
        assert resp.status_code == 403

    def test_audit_verify_is_scoped(self, secured):
        resp = secured.get(
            "/v1/audit/verify?workspace_id=globex", headers={"X-API-Key": "k-acme"}
        )
        assert resp.status_code == 403
