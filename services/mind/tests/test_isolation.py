"""Tenant isolation: search/get must scope by workspace_id."""

import pytest
import pytest_asyncio
from mind.search import HybridSearcher
from mind.storage import KnowledgeStore, _cosine


def test_cosine_identity():
    v = [1.0, 0.0, 0.0]
    assert _cosine(v, v) == pytest.approx(1.0)


def test_cosine_orthogonal():
    assert _cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


class StubEmbedder:
    async def embed(self, text: str):
        # Distinct axes so A/B vectors cannot rank each other first.
        if "alpha-secret" in text:
            return [1.0, 0.0] + [0.0] * 766
        if "beta-secret" in text:
            return [0.0, 1.0] + [0.0] * 766
        return [0.0] * 768


@pytest_asyncio.fixture
async def store():
    knowledge = KnowledgeStore()
    await knowledge.init(db_url="sqlite+aiosqlite://")
    yield knowledge
    await knowledge.close()


@pytest.mark.asyncio
async def test_keyword_and_get_do_not_cross_workspaces(store):
    await store.save({
        "id": "a1", "workspace_id": "ws-a", "type": "document",
        "content": "alpha-secret handbook expenses", "embedding": [1.0, 0.0] + [0.0] * 766,
    })
    await store.save({
        "id": "b1", "workspace_id": "ws-b", "type": "document",
        "content": "beta-secret runbook rollback", "embedding": [0.0, 1.0] + [0.0] * 766,
    })

    assert await store.get("a1", "ws-a") is not None
    assert await store.get("a1", "ws-b") is None
    assert await store.get("b1", "ws-a") is None

    a_hits = await store.search_by_keyword("secret", "ws-a")
    b_hits = await store.search_by_keyword("secret", "ws-b")
    assert [h["id"] for h in a_hits] == ["a1"]
    assert [h["id"] for h in b_hits] == ["b1"]
    assert "beta-secret" not in a_hits[0]["content"]
    assert "alpha-secret" not in b_hits[0]["content"]


@pytest.mark.asyncio
async def test_vector_search_and_hybrid_do_not_cross_workspaces(store):
    await store.save({
        "id": "a1", "workspace_id": "ws-a", "type": "document",
        "content": "alpha-secret handbook expenses", "embedding": [1.0, 0.0] + [0.0] * 766,
    })
    await store.save({
        "id": "b1", "workspace_id": "ws-b", "type": "document",
        "content": "beta-secret runbook rollback", "embedding": [0.0, 1.0] + [0.0] * 766,
    })

    a_vec = await store.search_by_vector([1.0, 0.0] + [0.0] * 766, "ws-a")
    b_vec = await store.search_by_vector([1.0, 0.0] + [0.0] * 766, "ws-b")
    assert [h["id"] for h in a_vec] == ["a1"]
    assert "a1" not in [h["id"] for h in b_vec]

    searcher = HybridSearcher(store, StubEmbedder())
    mixed = await searcher.search("alpha-secret handbook", filters=None, workspace_id="ws-b", top_k=10)
    assert all(hit["id"] != "a1" for hit in mixed)
    assert all("alpha-secret" not in hit.get("content", "") for hit in mixed)
