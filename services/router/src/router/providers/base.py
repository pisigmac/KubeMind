from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from router.circuit import CircuitBreaker, CircuitState


class BaseProvider(ABC):
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.healthy = True
        self.last_health_check = 0

        cb = config.get("circuit_breaker", {}) or {}
        self._breaker = CircuitBreaker(
            name,
            failure_threshold=int(cb.get("failure_threshold", 5)),
            recovery_timeout=float(cb.get("recovery_timeout_seconds", 30)),
            half_open_max=int(cb.get("half_open_max_requests", 3)),
        )

        # Observed latency, exponentially weighted. The `latency` routing
        # policy previously sorted on `timeout_seconds`, which is a ceiling the
        # operator guessed, not a measurement -- it ranked providers by how
        # patient we are with them.
        self.latency_ewma: Optional[float] = None
        self.latency_samples = 0
        self._latency_alpha = 0.2

        # Pricing (per 1K tokens, rough estimates)
        self.pricing = config.get("pricing", {
            "input": 0.0 if config.get("free") else 0.0015,
            "output": 0.0 if config.get("free") else 0.002,
        })

    def bind_circuit_redis(self, redis_client: Any) -> None:
        """Share breaker state across replicas. Safe to call with None."""
        self._breaker.bind_redis(redis_client)

    # ── Circuit breaker surface (kept for existing callers/tests) ─

    @property
    def circuit_state(self) -> CircuitState:
        return self._breaker.state

    @circuit_state.setter
    def circuit_state(self, value: CircuitState) -> None:
        self._breaker._state = value

    @property
    def failure_count(self) -> int:
        return self._breaker.failure_count

    @failure_count.setter
    def failure_count(self, value: int) -> None:
        self._breaker._failure_count = int(value)

    @property
    def success_count(self) -> int:
        return self._breaker._success_count

    @success_count.setter
    def success_count(self, value: int) -> None:
        self._breaker._success_count = int(value)

    @property
    def last_failure_time(self) -> float:
        return self._breaker._last_failure_time

    @last_failure_time.setter
    def last_failure_time(self, value: float) -> None:
        self._breaker._last_failure_time = float(value)

    @property
    def failure_threshold(self) -> int:
        return self._breaker.failure_threshold

    @property
    def recovery_timeout(self) -> float:
        return self._breaker.recovery_timeout

    @property
    def half_open_max(self) -> int:
        return self._breaker.half_open_max

    @abstractmethod
    async def chat(self, request: Any) -> Dict:
        pass

    @abstractmethod
    async def embeddings(self, request: Any) -> Dict:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass

    def can_execute(self) -> bool:
        return self._breaker.can_execute()

    async def can_execute_async(self) -> bool:
        return await self._breaker.can_execute_async()

    def record_success(self):
        self.healthy = True
        self._breaker.record_success()

    async def record_success_async(self):
        self.healthy = True
        await self._breaker.record_success_async()

    def record_failure(self):
        self._breaker.record_failure()
        if self._breaker.state == CircuitState.OPEN:
            self.healthy = False

    async def record_failure_async(self):
        await self._breaker.record_failure_async()
        if self._breaker.state == CircuitState.OPEN:
            self.healthy = False

    def observe_latency(self, latency_ms: float):
        if latency_ms is None or latency_ms <= 0:
            return
        self.latency_samples += 1
        if self.latency_ewma is None:
            self.latency_ewma = float(latency_ms)
        else:
            a = self._latency_alpha
            self.latency_ewma = a * float(latency_ms) + (1 - a) * self.latency_ewma

    @property
    def observed_latency_ms(self) -> Optional[float]:
        """Measured latency, or None when this provider has not been used.

        Returning None rather than a guess matters: callers filtering on a
        latency budget must not evict a provider on the strength of a number
        nobody measured.
        """
        return self.latency_ewma

    @property
    def quality_rank(self) -> int:
        """Explicit quality ordering, lower is better.

        Separate from `priority`, which expresses cost preference. Without its
        own field the `quality` policy just re-sorted by cost and the two
        policies were indistinguishable.
        """
        rank = self.config.get("quality_rank")
        if rank is None:
            return self.config.get("priority", 99)
        return int(rank)

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (prompt_tokens * self.pricing["input"] + completion_tokens * self.pricing["output"]) / 1000
