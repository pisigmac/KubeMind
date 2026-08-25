import os
import json
import redis.asyncio as redis
from typing import Optional, Dict


try:
    from kubemind_config import get_redis_url
except ImportError:
    def get_redis_url(default=None):
        return os.environ.get("REDIS_URL", default or "redis://localhost:6379/0")


class CacheManager:
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self.is_connected = False
        self._redis_url = get_redis_url()

    async def connect(self):
        try:
            if not self.client:
                self.client = redis.from_url(self._redis_url, decode_responses=True)
            await self.client.ping()
            self.is_connected = True
            print("[router] Redis cache connected")
        except Exception as e:
            print(f"[router] Redis connection failed: {e}. Running without cache.")
            self.is_connected = False
            self.client = None

    async def disconnect(self):
        if self.client:
            await self.client.close()
            self.is_connected = False

    async def get(self, key: str) -> Optional[Dict]:
        if not self.is_connected or not self.client:
            return None
        try:
            data = await self.client.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    async def set(self, key: str, value: Dict, ttl: int = 300):
        if not self.is_connected or not self.client:
            return
        try:
            await self.client.setex(key, ttl, json.dumps(value))
        except Exception:
            pass

    async def delete(self, key: str):
        if not self.is_connected or not self.client:
            return
        try:
            await self.client.delete(key)
        except Exception:
            pass

    async def clear(self):
        if not self.is_connected or not self.client:
            return
        try:
            await self.client.flushdb()
        except Exception:
            pass

    async def stats(self) -> Dict:
        if not self.is_connected or not self.client:
            return {"connected": False}
        try:
            info = await self.client.info()
            db_size = await self.client.dbsize()
            return {
                "connected": True,
                "keys_in_db": db_size,
                "used_memory_human": info.get("used_memory_human", "N/A"),
                "redis_version": info.get("redis_version", "N/A"),
            }
        except Exception as e:
            return {"connected": True, "error": str(e)}
