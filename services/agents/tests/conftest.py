import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def mock_tools():
    tools = MagicMock()
    tools.tools = {"filesystem": MagicMock(), "shell": MagicMock()}
    tools.invoke = AsyncMock(return_value={"result": "ok"})
    tools.list_schema = MagicMock(return_value=[])
    return tools

@pytest.fixture
async def mock_planner():
    planner = MagicMock()
    planner.init = AsyncMock()
    planner.plan = AsyncMock(return_value={
        "todos": [
            {"step": 1, "task": "Do something", "tool": None, "reasoning": "Direct"},
        ],
        "estimated_steps": 1,
    })
    planner.close = AsyncMock()
    return planner

@pytest.fixture
async def mock_memory():
    memory = MagicMock()
    memory.init = AsyncMock()
    memory.read = AsyncMock(return_value=[])
    memory.write = AsyncMock(return_value="mem-id")
    memory.ingest_conversation = AsyncMock(return_value="conv-id")
    memory.close = AsyncMock()
    return memory
