import json
import pytest
from unittest.mock import AsyncMock

from router.cache.semantic import cosine_similarity, cosine_distance, SemanticCache


class TestCosine:
    def test_identical_vectors(self):
        v = [1.0, 0.0, 0.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)
        assert cosine_distance(v, v) == pytest.approx(0.0)

    def test_orthogonal(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)
        assert cosine_distance(a, b) == pytest.approx(1.0)

    def test_near_duplicate_below_threshold(self):
        a = [1.0, 0.1, 0.0]
        b = [1.0, 0.12, 0.0]
        dist = cosine_distance(a, b)
        assert dist < 0.05

    def test_empty_safe(self):
        assert cosine_similarity([], [1.0]) == 0.0
        assert cosine_distance([1.0], [1.0, 2.0]) == 1.0


class TestSemanticCacheConfig:
    def test_from_config_defaults(self):
        sc = SemanticCache.from_config(
            {
                "cache": {
                    "ttl_seconds": 120,
                    "semantic": {
                        "enabled": True,
                        "distance_threshold": 0.05,
                    },
                }
            }
        )
        assert sc.enabled is True
        assert sc.distance_threshold == 0.05
        assert sc.ttl_seconds == 120

    def test_from_config_disabled(self):
        sc = SemanticCache.from_config({"cache": {"semantic": {"enabled": False}}})
        assert sc.enabled is False


class TestEmbeddingNamespace:
    """Vectors from different models or prefixes are not comparable."""

    def test_prefix_change_rolls_the_namespace(self):
        a = SemanticCache(embedding_prefix="search_query: ")
        b = SemanticCache(embedding_prefix="classification: ")
        assert a.embedding_namespace != b.embedding_namespace
        assert a._list_key("ws") != b._list_key("ws")

    def test_model_change_rolls_the_namespace(self):
        a = SemanticCache(embedding_model="nomic-embed-text")
        b = SemanticCache(embedding_model="mxbai-embed-large")
        assert a._list_key("ws") != b._list_key("ws")

    def test_same_settings_share_a_namespace(self):
        assert SemanticCache()._list_key("ws") == SemanticCache()._list_key("ws")

    def test_intent_partition_nests_under_namespace(self):
        sc = SemanticCache()
        assert sc._list_key("ws", "code").startswith(sc._list_key("ws"))

    def test_prefix_is_configurable(self):
        sc = SemanticCache.from_config(
            {"cache": {"semantic": {"embedding_prefix": "classification: "}}}
        )
        assert sc.embedding_prefix == "classification: "

    @pytest.mark.asyncio
    async def test_prefix_is_applied_to_the_embed_call(self, monkeypatch):
        sent = {}

        class FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"embedding": [0.1, 0.2]}

        class FakeClient:
            async def post(self, url, json=None):
                sent.update(json or {})
                return FakeResp()

        sc = SemanticCache(embedding_prefix="search_query: ")
        monkeypatch.setattr(sc, "_http_client", AsyncMock(return_value=FakeClient()))
        await sc.embed("why is my pod crashing")
        assert sent["prompt"] == "search_query: why is my pod crashing"


class TestSemanticCacheLookup:
    @pytest.mark.asyncio
    async def test_lookup_hit(self, mock_redis):
        emb = [1.0, 0.0, 0.0]
        entry = {
            "embedding": emb,
            "response": {
                "choices": [{"message": {"content": "cached"}}],
                "model": "m",
            },
            "model": "m",
        }
        mock_redis.lrange = AsyncMock(return_value=[json.dumps(entry)])

        sc = SemanticCache(redis_client=mock_redis, distance_threshold=0.05)
        sc.is_ready = True
        hit = await sc.lookup("default", emb)
        assert hit is not None
        payload, dist, meta = hit
        assert dist == pytest.approx(0.0)
        assert payload["choices"][0]["message"]["content"] == "cached"
        assert meta["model"] == "m"

    @pytest.mark.asyncio
    async def test_lookup_miss(self, mock_redis):
        entry = {
            "embedding": [1.0, 0.0, 0.0],
            "response": {"choices": []},
            "model": "m",
        }
        mock_redis.lrange = AsyncMock(return_value=[json.dumps(entry)])
        sc = SemanticCache(redis_client=mock_redis, distance_threshold=0.01)
        hit = await sc.lookup("default", [0.0, 1.0, 0.0])
        assert hit is None
