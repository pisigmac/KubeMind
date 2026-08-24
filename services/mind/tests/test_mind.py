import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

@pytest.fixture
def secured_client(tmp_path, monkeypatch):
    monkeypatch.setenv("KUBEMIND_API_KEYS", "k-admin:acme:admin,k-viewer:acme:viewer,k-auditor:acme:auditor,k-dev:acme:developer")
    monkeypatch.setenv("KUBEMIND_MIND_CONFIG", "")
    
    with patch("mind.storage.KnowledgeStore.init", new_callable=AsyncMock), \
         patch("mind.storage.KnowledgeStore.close", new_callable=AsyncMock), \
         patch("mind.storage.KnowledgeStore.save", new_callable=AsyncMock, return_value="node1"), \
         patch("mind.embeddings.EmbeddingGenerator.init", new_callable=AsyncMock), \
         patch("mind.embeddings.EmbeddingGenerator.close", new_callable=AsyncMock), \
         patch("mind.embeddings.EmbeddingGenerator.embed", new_callable=AsyncMock, return_value=[0.1]*768):

        import importlib
        from mind import main
        importlib.reload(main)
        
        with TestClient(main.app) as c:
            yield c
        
        importlib.reload(main)

def test_mind_rbac_enforcement(secured_client):
    # viewer tries to query (mind:query required)
    assert secured_client.post("/v1/query", json={"query": "test"}, headers={"X-API-Key": "k-viewer"}).status_code == 403
    
    # auditor tries to ingest (mind:ingest required)
    assert secured_client.post("/v1/ingest", json={"source": "test", "type": "document", "content": "test"}, headers={"X-API-Key": "k-auditor"}).status_code == 403
    
    # developer tries to query and ingest (developer has mind:query, mind:ingest)
    resp_query = secured_client.post("/v1/query", json={"query": "test"}, headers={"X-API-Key": "k-dev"})
    assert resp_query.status_code != 403

    resp_ingest = secured_client.post("/v1/ingest", json={"source": "test", "type": "document", "content": "text"}, headers={"X-API-Key": "k-dev"})
    assert resp_ingest.status_code != 403
