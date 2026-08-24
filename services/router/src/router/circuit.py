"""Redis-backed circuit breaker state.

Per-process breakers diverge across replicas: one pod can be OPEN while
another is CLOSED for the same upstream, which produces flapping that no
single process can explain. Shared state in Redis makes the decision cluster-
wide. When Redis is unavailable the breaker falls back to in-process memory
so a cache outage does not take providers offline with it.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max: int = 3,
        redis_client: Any = None,
        key_prefix: str = "km:cb",
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max
        self.redis = redis_client
        self.key = f"{key_prefix}:{name}"

        # Local mirror used when Redis is down, and as a write-through cache
        # so can_execute stays cheap on the hot path.
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def bind_redis(self, client: Any) -> None:
        self.redis = client

    async def sync(self) -> None:
        """Pull shared state into the local mirror. Best-effort."""
        if not self.redis:
            return
        try:
            data = await self.redis.hgetall(self.key)
            if not data:
                return
            # decode_responses may or may not be on; normalise to str.
            data = {
                (k.decode() if isinstance(k, bytes) else k): (
                    v.decode() if isinstance(v, bytes) else v
                )
                for k, v in data.items()
            }
            self._state = CircuitState(data.get("state", "closed"))
            self._failure_count = int(data.get("failures", 0))
            self._success_count = int(data.get("successes", 0))
            self._last_failure_time = float(data.get("last_failure", 0))
        except Exception:
            pass

    async def _persist(self) -> None:
        if not self.redis:
            return
        try:
            await self.redis.hset(
                self.key,
                mapping={
                    "state": self._state.value,
                    "failures": str(self._failure_count),
                    "successes": str(self._success_count),
                    "last_failure": str(self._last_failure_time),
                },
            )
            # Keep the key around longer than any recovery window so a quiet
            # provider does not silently lose its OPEN state.
            await self.redis.expire(self.key, int(self.recovery_timeout * 10) + 300)
        except Exception:
            pass

    def can_execute(self) -> bool:
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time > self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
                self._failure_count = 0
                return True
            return False
        if self._state == CircuitState.HALF_OPEN:
            return self._success_count < self.half_open_max
        return False

    async def can_execute_async(self) -> bool:
        await self.sync()
        return self.can_execute()

    def record_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.half_open_max:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
        else:
            self._failure_count = 0

    async def record_success_async(self) -> None:
        await self.sync()
        self.record_success()
        await self._persist()

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN

    async def record_failure_async(self) -> None:
        await self.sync()
        self.record_failure()
        await self._persist()
