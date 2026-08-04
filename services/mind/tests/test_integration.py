import pytest
from fastapi.testclient import TestClient

class TestIntegration:
    @pytest.mark.skip(reason="Requires running Ollama + PostgreSQL")
    def test_full_ingest_and_query(self):
        from mind.main import app
        client = TestClient(app)

        # Ingest a document
        resp = client.post("/v1/ingest", json={
            "source": "./test-docs",
            "type": "document",
        }, headers={"X-Workspace-ID": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ingested"] > 0

        # Query it
        resp = client.post("/v1/query", json={
            "query": "test",
            "top_k": 5,
        }, headers={"X-Workspace-ID": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data

    def test_health(self):
        from mind.main import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "mind"
