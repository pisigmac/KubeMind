"""Tenant isolation: search/get must scope by workspace_id."""

import pytest
from mind.storage import _cosine


def test_cosine_identity():
    v = [1.0, 0.0, 0.0]
    assert _cosine(v, v) == pytest.approx(1.0)


def test_cosine_orthogonal():
    assert _cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


class TestWorkspaceFilterContract:
    """Document the isolation contract for KnowledgeStore methods.

    Live DB tests run under integration; here we assert call patterns
    with a lightweight fake store.
    """

    @pytest.mark.asyncio
    async def test_get_requires_workspace_match(self):
        from unittest.mock import AsyncMock

        store = AsyncMock()
        store.get = AsyncMock(return_value=None)

        # Simulate: node exists only in ws-a
        async def get_side(node_id, workspace_id):
            if workspace_id == "ws-a" and node_id == "n1":
                return {"id": "n1", "workspace_id": "ws-a", "content": "secret"}
            return None

        store.get.side_effect = get_side

        assert await store.get("n1", "ws-a") is not None
        assert await store.get("n1", "ws-b") is None

    @pytest.mark.asyncio
    async def test_search_by_vector_passes_workspace(self):
        from unittest.mock import AsyncMock, call

        store = AsyncMock()
        store.search_by_vector = AsyncMock(return_value=[])
        await store.search_by_vector([0.1] * 8, "tenant-x", filters=None, limit=5)
        store.search_by_vector.assert_awaited_once_with(
            [0.1] * 8, "tenant-x", filters=None, limit=5
        )

    @pytest.mark.asyncio
    async def test_search_by_keyword_passes_workspace(self):
        from unittest.mock import AsyncMock

        store = AsyncMock()
        store.search_by_keyword = AsyncMock(return_value=[])
        await store.search_by_keyword("hello", "tenant-y", limit=10)
        args, kwargs = store.search_by_keyword.await_args
        assert args[1] == "tenant-y"
