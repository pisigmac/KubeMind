"""Redis-backed circuit breaker."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from router.circuit import CircuitBreaker, CircuitState


@pytest.mark.asyncio
async def test_opens_after_threshold():
    cb = CircuitBreaker("ollama", failure_threshold=2, recovery_timeout=60)
    assert cb.can_execute() is True
    await cb.record_failure_async()
    assert cb.state == CircuitState.CLOSED
    await cb.record_failure_async()
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False


@pytest.mark.asyncio
async def test_recovers_to_half_open():
    cb = CircuitBreaker("ollama", failure_threshold=1, recovery_timeout=0)
    await cb.record_failure_async()
    assert cb.state == CircuitState.OPEN
    # recovery_timeout=0 means the next can_execute flips to half-open.
    assert cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_persists_to_redis():
    redis = MagicMock()
    redis.hgetall = AsyncMock(return_value={})
    redis.hset = AsyncMock()
    redis.expire = AsyncMock()
    cb = CircuitBreaker("groq", failure_threshold=1, redis_client=redis)
    await cb.record_failure_async()
    redis.hset.assert_awaited()
    mapping = redis.hset.await_args.kwargs["mapping"]
    assert mapping["state"] == "open"


@pytest.mark.asyncio
async def test_syncs_from_redis():
    redis = MagicMock()
    redis.hgetall = AsyncMock(
        return_value={
            "state": "open",
            "failures": "5",
            "successes": "0",
            "last_failure": str(10**18),
        }
    )
    cb = CircuitBreaker("openai", redis_client=redis)
    await cb.sync()
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False
