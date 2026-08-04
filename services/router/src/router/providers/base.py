import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class BaseProvider(ABC):
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.healthy = True
        self.last_health_check = 0

        # Circuit breaker state
        self.circuit_state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.failure_threshold = config.get("circuit_breaker", {}).get("failure_threshold", 5)
        self.recovery_timeout = config.get("circuit_breaker", {}).get("recovery_timeout_seconds", 30)
        self.half_open_max = config.get("circuit_breaker", {}).get("half_open_max_requests", 3)

        # Pricing (per 1K tokens, rough estimates)
        self.pricing = config.get("pricing", {
            "input": 0.0 if config.get("free") else 0.0015,
            "output": 0.0 if config.get("free") else 0.002,
        })

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
        if self.circuit_state == CircuitState.CLOSED:
            return True
        if self.circuit_state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.circuit_state = CircuitState.HALF_OPEN
                self.success_count = 0
                self.failure_count = 0
                return True
            return False
        if self.circuit_state == CircuitState.HALF_OPEN:
            return self.success_count < self.half_open_max
        return False

    def record_success(self):
        self.healthy = True
        if self.circuit_state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_max:
                self.circuit_state = CircuitState.CLOSED
                self.failure_count = 0
        else:
            self.failure_count = 0

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.circuit_state == CircuitState.HALF_OPEN:
            self.circuit_state = CircuitState.OPEN
        elif self.failure_count >= self.failure_threshold:
            self.circuit_state = CircuitState.OPEN
            self.healthy = False

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (prompt_tokens * self.pricing["input"] + completion_tokens * self.pricing["output"]) / 1000
