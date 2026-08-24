import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_redis():
    client = MagicMock()
    client.ping = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value=None)
    client.setex = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.flushdb = AsyncMock(return_value=True)
    pipe = MagicMock()
    pipe.get = MagicMock(return_value=pipe)
    pipe.set = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[None, None])
    client.pipeline = MagicMock(return_value=pipe)
    client.hincrby = AsyncMock(return_value=1)
    client.expire = AsyncMock(return_value=True)
    client.dbsize = AsyncMock(return_value=0)
    client.info = AsyncMock(return_value={"used_memory_human": "1M", "redis_version": "7.0"})
    client.close = AsyncMock()
    client.lrange = AsyncMock(return_value=[])
    client.lpush = AsyncMock(return_value=1)
    client.ltrim = AsyncMock(return_value=True)
    return client
