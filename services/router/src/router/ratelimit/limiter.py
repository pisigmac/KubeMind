import time
from typing import Tuple, Dict


TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local refill_per_ms = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])
local tokens = tonumber(redis.call('HGET', key, 'tokens') or capacity)
local updated = tonumber(redis.call('HGET', key, 'updated_ms') or now_ms)
local elapsed = math.max(0, now_ms - updated)
tokens = math.min(capacity, tokens + (elapsed * refill_per_ms))
local allowed = 0
local retry_ms = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
else
  retry_ms = math.ceil((cost - tokens) / refill_per_ms)
end
redis.call('HSET', key, 'tokens', tokens, 'updated_ms', now_ms)
redis.call('EXPIRE', key, 120)
return {allowed, retry_ms}
"""

class RateLimiter:
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.default_rpm = 60
        self.default_tpm = 10000

    async def check(self, workspace_id: str, model: str) -> Tuple[bool, int]:
        if not self.redis:
            return True, 0

        now_ms = int(time.time() * 1000)
        key = f"ratelimit:{workspace_id}:{model}"
        capacity = self.default_rpm * 1000
        refill_per_ms = capacity / 60_000
        allowed, retry_ms = await self.redis.eval(
            TOKEN_BUCKET_SCRIPT,
            1,
            key,
            now_ms,
            capacity,
            refill_per_ms,
            1000,
        )
        return bool(allowed), (int(retry_ms) + 999) // 1000

    async def record(self, workspace_id: str, model: str, usage: Dict[str, int]):
        if not self.redis:
            return

        key = f"usage:{workspace_id}:{model}"
        pipe = self.redis.pipeline()
        pipe.hincrby(key, "requests", 1)
        pipe.hincrby(key, "tokens", usage.get("total_tokens", 0))
        pipe.expire(key, 86400)  # 24h TTL
        await pipe.execute()
