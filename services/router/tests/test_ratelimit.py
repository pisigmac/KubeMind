import pytest
from unittest.mock import AsyncMock, MagicMock
from router.ratelimit import RateLimiter

class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_check_allowed(self):
        redis = MagicMock()
        redis.eval = AsyncMock(return_value=[1, 0])

        limiter = RateLimiter(redis_client=redis)
        allowed, retry = await limiter.check("ws-1", "llama3.1")
        assert allowed is True
        assert retry == 0
        redis.eval.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_denied_uses_atomic_retry(self):
        redis = MagicMock()
        redis.eval = AsyncMock(return_value=[0, 1500])
        limiter = RateLimiter(redis_client=redis)
        allowed, retry = await limiter.check("ws-1", "llama3.1")
        assert allowed is False
        assert retry == 2

    @pytest.mark.asyncio
    async def test_record_usage(self):
        redis = MagicMock()
        redis.pipeline = MagicMock(return_value=redis)
        redis.execute = AsyncMock(return_value=[1, 1, 1])

        limiter = RateLimiter(redis_client=redis)
        await limiter.record("ws-1", "llama3.1", {"total_tokens": 100})
        redis.hincrby.assert_called()
