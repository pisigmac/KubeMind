import pytest
from unittest.mock import AsyncMock, MagicMock
from mind.search import HybridSearcher

class TestHybridSearcher:
    @pytest.fixture
    def searcher(self, mock_store, mock_embedder):
        return HybridSearcher(mock_store, mock_embedder)

    @pytest.mark.asyncio
    async def test_search_combines_scores(self, searcher, mock_store, mock_embedder):
        mock_embedder.embed = AsyncMock(return_value=[0.1] * 768)

        mock_store.search_by_vector = AsyncMock(return_value=[
            {"id": "v1", "type": "doc", "content": "vector match", "metadata": {}, "score": 0.9},
        ])
        mock_store.search_by_keyword = AsyncMock(return_value=[
            {"id": "k1", "type": "doc", "content": "keyword match", "metadata": {}, "score": 5},
        ])
        mock_store.get_links = AsyncMock(return_value=[])

        results = await searcher.search("test query", None, "default", top_k=5)

        assert len(results) > 0
        mock_embedder.embed.assert_called_once_with("test query")
        mock_store.search_by_vector.assert_called_once()
        mock_store.search_by_keyword.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_filters(self, searcher, mock_store, mock_embedder):
        mock_embedder.embed = AsyncMock(return_value=[0.1] * 768)
        mock_store.search_by_vector = AsyncMock(return_value=[])
        mock_store.search_by_keyword = AsyncMock(return_value=[])

        await searcher.search("test", {"type": "code"}, "default", top_k=5)

        # Verify filters passed through
        call_args = mock_store.search_by_vector.call_args
        assert call_args[0][2] == {"type": "code"}

    def test_merge_results(self, searcher):
        vector = [{"id": "1", "type": "doc", "content": "a", "metadata": {}, "score": 0.9}]
        keyword = [{"id": "1", "type": "doc", "content": "a", "metadata": {}, "score": 5}]
        graph = []

        merged = searcher._merge_results(vector, keyword, graph)
        assert len(merged) == 1
        assert merged[0]["id"] == "1"
        assert merged[0]["score"] > 0  # Combined score should be positive
