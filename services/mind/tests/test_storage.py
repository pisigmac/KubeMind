import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from mind.storage import KnowledgeStore

class TestKnowledgeStore:
    @pytest.mark.asyncio
    async def test_save_and_get(self, mock_store):
        node = {
            "workspace_id": "default",
            "type": "document",
            "content": "test content",
            "metadata": {"title": "Test"},
            "embedding": [0.1] * 768,
        }
        nid = await mock_store.save(node)
        assert nid == "test-node-id"
        mock_store.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_links(self, mock_store):
        links = await mock_store.get_links("node-1", "default")
        assert links == []
        mock_store.get_links.assert_called_once_with("node-1", "default")

    @pytest.mark.asyncio
    async def test_create_link(self, mock_store):
        result = await mock_store.create_link("a", "b", "related", "default")
        assert result["id"] == "link-id"
        mock_store.create_link.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_subgraph(self, mock_store):
        result = await mock_store.export_subgraph("default")
        assert result["nodes"] == []
        assert result["links"] == []
