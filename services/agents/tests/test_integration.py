import pytest
from fastapi.testclient import TestClient

class TestIntegration:
    @pytest.mark.skip(reason="Requires full stack: Ollama + PostgreSQL + mind")
    def test_end_to_end_mission(self):
        from agents.main import app
        client = TestClient(app)

        # Create mission
        resp = client.post("/v1/missions", json={
            "prompt": "Write a Python function to calculate factorial",
            "mode": "sync",
        }, headers={"X-Workspace-ID": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "factorial" in data["result"].lower() or "def" in data["result"].lower()

    def test_health(self):
        from agents.main import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "agents"

    def test_list_tools(self):
        from agents.main import app
        client = TestClient(app)
        resp = client.get("/v1/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
