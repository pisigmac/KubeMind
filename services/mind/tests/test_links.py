import pytest
from unittest.mock import AsyncMock, MagicMock
from mind.links import LinkDetector

class TestLinkDetector:
    @pytest.fixture
    def detector(self, mock_store):
        return LinkDetector(mock_store)

    @pytest.mark.asyncio
    async def test_detect_semantic_links(self, detector, mock_store):
        mock_store.get = AsyncMock(return_value={
            "id": "new-1",
            "type": "document",
            "content": "hello world",
            "metadata": {},
            "embedding": [0.9] * 768,
        })
        mock_store.get_all_nodes = AsyncMock(return_value=[
            {"id": "existing-1", "type": "document", "content": "hello world", "metadata": {}, "embedding": [0.91] * 768},
        ])

        await detector.detect_links(["new-1"], "default")
        mock_store.create_link.assert_called()

    @pytest.mark.asyncio
    async def test_detect_same_repo_links(self, detector, mock_store):
        mock_store.get = AsyncMock(return_value={
            "id": "new-1",
            "type": "code",
            "content": "def foo()",
            "metadata": {"repo": "/path/to/repo"},
            "embedding": None,
        })
        mock_store.get_all_nodes = AsyncMock(return_value=[
            {"id": "existing-1", "type": "code", "content": "def bar()", "metadata": {"repo": "/path/to/repo"}, "embedding": None},
        ])

        await detector.detect_links(["new-1"], "default")
        mock_store.create_link.assert_called()

    def test_cosine_similarity(self, detector):
        a = [1.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        assert detector._cosine_similarity(a, b) == 1.0

        c = [0.0, 1.0, 0.0]
        assert detector._cosine_similarity(a, c) == 0.0

    def test_find_shared_entities(self, detector):
        node_a = {"metadata": {"source_url": "http://example.com"}, "content": "hello world foo bar"}
        node_b = {"metadata": {"source_url": "http://example.com"}, "content": "hello world baz qux"}
        shared = detector._find_shared_entities(node_a, node_b)
        assert "http://example.com" in shared
