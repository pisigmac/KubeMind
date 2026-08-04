import pytest
from fastapi.testclient import TestClient

class TestIntegration:
    def test_health(self):
        from sentinel.main import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "sentinel"

    def test_ingest_and_query(self):
        from sentinel.main import app
        client = TestClient(app)

        # Ingest a span
        resp = client.post("/v1/spans", json={
            "trace_id": "trace-1",
            "span_id": "span-1",
            "workspace_id": "test",
            "service": "router",
            "operation": "llm_call",
            "start_time": "2024-01-01T00:00:00",
            "status": "ok",
            "attributes": {"model": "llama3.1"},
        })
        assert resp.status_code == 200

        # Query it back
        resp = client.get("/v1/spans?workspace_id=test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["spans"][0]["service"] == "router"

    def test_metrics(self):
        from sentinel.main import app
        client = TestClient(app)

        resp = client.get("/v1/metrics?workspace_id=test")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_spans" in data
        assert "services" in data

    def test_export(self):
        from sentinel.main import app
        client = TestClient(app)

        resp = client.get("/v1/export?workspace_id=test")
        assert resp.status_code == 200
        data = resp.json()
        assert "spans" in data
        assert "count" in data
