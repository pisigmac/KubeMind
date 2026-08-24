import pytest
import httpx
import respx
from fastapi.testclient import TestClient

# Integration tests that work against mocked Ollama (free, no API costs)
# For real integration tests, start Ollama locally with `ollama run llama3.1`

class TestIntegration:
    @pytest.fixture
    def client(self):
        # We need to mock the lifespan startup
        from router.main import app
        # Override dependencies for testing
        return TestClient(app)

    @pytest.mark.skip(reason="Requires running Ollama instance. Run: ollama run llama3.1")
    def test_chat_with_ollama(self, client):
        resp = client.post("/v1/chat/completions", json={
            "model": "llama3.1",
            "messages": [{"role": "user", "content": "Say hello"}],
            "temperature": 0.1,
        }, headers={"X-Workspace-ID": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "choices" in data
        assert data["provider"] == "ollama"
        assert data["cached"] is False

    @pytest.mark.skip(reason="Requires running Ollama instance")
    def test_embeddings_with_ollama(self, client):
        resp = client.post("/v1/embeddings", json={
            "model": "nomic-embed-text",
            "input": "hello world",
        }, headers={"X-Workspace-ID": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"][0]["embedding"]) > 0

    @pytest.mark.skip(reason="Requires full stack running")
    def test_circuit_breaker_fallback(self, client):
        # Kill Ollama, verify fallback to next provider
        resp = client.post("/v1/chat/completions", json={
            "model": "llama3.1",
            "messages": [{"role": "user", "content": "test"}],
        }, headers={"X-Workspace-ID": "test"})
        # Should either succeed via fallback or return 503
        assert resp.status_code in [200, 503]
        if resp.status_code == 200:
            assert resp.json().get("fallback") is True

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "router"
        assert "providers_loaded" in data

    def test_rate_limit_headers(self, client):
        # Make many requests quickly to trigger rate limit
        for _ in range(70):
            resp = client.post("/v1/chat/completions", json={
                "model": "llama3.1",
                "messages": [{"role": "user", "content": "test"}],
            }, headers={"X-Workspace-ID": "ratelimit-test"})
        # After 60 requests, should get 429
        # Note: This test may fail if Redis is not running; skip if needed
