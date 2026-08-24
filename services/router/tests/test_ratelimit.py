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

class TestRateLimiterTPM:
    """Verify token-per-minute throttling."""

    @pytest.mark.asyncio
    async def test_tpm_check_blocks_when_exceeded(self):
        limiter = RateLimiter(redis_client=None, default_rpm=1000, default_tpm=100)
        limiter._local_tpm["test:gpt-4"] = 101
        allowed, retry_after = await limiter.check_tpm("test", "gpt-4", token_count=1)
        assert not allowed
        assert retry_after > 0

    @pytest.mark.asyncio
    async def test_tpm_check_allows_under_limit(self):
        limiter = RateLimiter(redis_client=None, default_rpm=1000, default_tpm=100)
        limiter._local_tpm["test:gpt-4"] = 50
        allowed, _ = await limiter.check_tpm("test", "gpt-4", token_count=1)
        assert allowed


class TestRateLimitHeaders:
    """Verify rate limit response headers are set."""

    def test_headers_contain_standard_fields(self):
        headers = RateLimiter.build_headers(limit=60, remaining=42, reset_seconds=30)
        assert headers["X-RateLimit-Limit"] == "60"
        assert headers["X-RateLimit-Remaining"] == "42"
        assert "X-RateLimit-Reset" in headers
        assert "Retry-After" not in headers

    def test_headers_include_retry_after_when_exceeded(self):
        headers = RateLimiter.build_headers(limit=60, remaining=0, reset_seconds=30, exceeded=True)
        assert headers["Retry-After"] == "30"
