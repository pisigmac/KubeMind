import time
from typing import Tuple, Dict, Any, Optional

class RateLimiter:
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.default_rpm = 60
        self.default_tpm = 10000

    async def check(self, workspace_id: str, model: str) -> Tuple[bool, int]:
        if not self.redis:
            return True, 0

        now = time.time()
        key = f"ratelimit:{workspace_id}:{model}"

        # Simple token bucket using Redis
        # tokens = min(capacity, tokens + elapsed * rate) - 1
        pipe = self.redis.pipeline()
        pipe.get(f"{key}:tokens")
        pipe.get(f"{key}:last_update")
        results = await pipe.execute()

        tokens = float(results[0]) if results[0] else self.default_rpm
        last_update = float(results[1]) if results[1] else now

        elapsed = now - last_update
        tokens = min(self.default_rpm, tokens + elapsed * (self.default_rpm / 60))

        if tokens >= 1:
            tokens -= 1
            pipe = self.redis.pipeline()
            pipe.set(f"{key}:tokens", str(tokens))
            pipe.set(f"{key}:last_update", str(now))
            await pipe.execute()
            return True, 0

        retry_after = int((1 - tokens) * 60 / self.default_rpm) + 1
        return False, retry_after

    async def record(self, workspace_id: str, model: str, usage: Dict[str, int]):
        if not self.redis:
            return

        key = f"usage:{workspace_id}:{model}"
        pipe = self.redis.pipeline()
        pipe.hincrby(key, "requests", 1)
        pipe.hincrby(key, "tokens", usage.get("total_tokens", 0))
        pipe.expire(key, 86400)  # 24h TTL
        await pipe.execute()
