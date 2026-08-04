import pytest
from unittest.mock import AsyncMock, MagicMock
from router.cache import CacheManager

class TestCacheManager:
    @pytest.mark.asyncio
    async def test_connect_success(self, mock_redis):
        cache = CacheManager()
        cache.client = mock_redis
        await cache.connect()
        assert cache.is_connected is True

    @pytest.mark.asyncio
    async def test_get_set(self, mock_redis):
        cache = CacheManager()
        cache.client = mock_redis
        cache.is_connected = True

        mock_redis.get = AsyncMock(return_value='{"key": "value"}')
        result = await cache.get("test-key")
        assert result == {"key": "value"}

        mock_redis.setex = AsyncMock(return_value=True)
        await cache.set("test-key", {"key": "value"}, ttl=300)
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear(self, mock_redis):
        cache = CacheManager()
        cache.client = mock_redis
        cache.is_connected = True

        await cache.clear()
        mock_redis.flushdb.assert_called_once()

    @pytest.mark.asyncio
    async def test_stats(self, mock_redis):
        cache = CacheManager()
        cache.client = mock_redis
        cache.is_connected = True

        mock_redis.dbsize = AsyncMock(return_value=42)
        mock_redis.info = AsyncMock(return_value={"used_memory_human": "2M", "redis_version": "7.2"})

        stats = await cache.stats()
        assert stats["connected"] is True
        assert stats["keys_in_db"] == 42
