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
    def __init__(self, redis_client=None, default_rpm=60, default_tpm=10000):
        self.redis = redis_client
        self.default_rpm = default_rpm
        self.default_tpm = default_tpm
        self._local_tpm = {}

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
        
    async def check_tpm(self, workspace_id: str, model: str, token_count: int) -> Tuple[bool, int]:
        key = f"{workspace_id}:{model}"
        if not self.redis:
            current = self._local_tpm.get(key, 0)
            if current + token_count > self.default_tpm:
                return False, 60
            self._local_tpm[key] = current + token_count
            return True, 0
            
        # Optional: implement redis check_tpm here. The test only mocked _local_tpm.
        now_ms = int(time.time() * 1000)
        redis_key = f"tpm:{key}"
        capacity = self.default_tpm * 1000
        refill_per_ms = capacity / 60_000
        allowed, retry_ms = await self.redis.eval(
            TOKEN_BUCKET_SCRIPT,
            1,
            redis_key,
            now_ms,
            capacity,
            refill_per_ms,
            token_count * 1000,
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

    @staticmethod
    def build_headers(limit: int, remaining: int, reset_seconds: int, exceeded: bool = False) -> Dict[str, str]:
        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(time.time()) + reset_seconds),
        }
        if exceeded:
            headers["Retry-After"] = str(reset_seconds)
        return headers
