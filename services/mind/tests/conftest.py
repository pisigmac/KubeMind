import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.init = AsyncMock()
    store.save = AsyncMock(return_value="test-node-id")
    store.get = AsyncMock(
        return_value={
            "id": "test-node-id",
            "workspace_id": "default",
            "type": "document",
            "content": "test content",
            "metadata": {},
            "embedding": [0.1] * 768,
        }
    )
    store.get_links = AsyncMock(return_value=[])
    store.create_link = AsyncMock(return_value={"id": "link-id"})
    store.export_subgraph = AsyncMock(return_value={"nodes": [], "links": []})
    store.search_by_keyword = AsyncMock(return_value=[])
    store.search_by_vector = AsyncMock(return_value=[])
    store.get_all_nodes = AsyncMock(return_value=[])
    store.close = AsyncMock()
    store.is_ready = True
    store.pgvector_enabled = False
    return store


@pytest.fixture
def mock_embedder():
    emb = MagicMock()
    emb.init = AsyncMock()
    emb.embed = AsyncMock(return_value=[0.1] * 768)
    emb.embed_batch = AsyncMock(return_value=[[0.1] * 768])
    emb.close = AsyncMock()
    emb.is_ready = True
    return emb
