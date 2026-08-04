import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.engine import AgentEngine

class TestAgentEngine:
    @pytest.fixture
    async def engine(self, mock_tools, mock_planner, mock_memory):
        engine = AgentEngine(tools=mock_tools, planner=mock_planner, memory=mock_memory)
        engine.session_maker = MagicMock()
        session = AsyncMock()
        engine.session_maker.return_value.__aenter__ = AsyncMock(return_value=session)
        engine.session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        engine.client = MagicMock()
        engine.client.post = AsyncMock(return_value=MagicMock(
            raise_for_status=MagicMock(),
            json=MagicMock(return_value={
                "choices": [{"message": {"content": "Result"}}],
                "usage": {"total_tokens": 10},
            })
        ))
        engine.is_ready = True
        return engine

    @pytest.mark.asyncio
    async def test_run_sync_success(self, engine, mock_planner):
        result = await engine.run_sync("Test mission", "default")
        assert result["status"] == "completed"
        assert "output" in result
        assert result["tool_calls"] >= 0
        assert result["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_run_sync_with_tools(self, engine, mock_tools):
        mock_planner.plan = AsyncMock(return_value={
            "todos": [
                {"step": 1, "task": "List files", "tool": "filesystem", "reasoning": "Need to see files"},
            ],
        })

        result = await engine.run_sync("List files", "default")
        assert result["status"] == "completed"
        mock_tools.invoke.assert_called()

    @pytest.mark.asyncio
    async def test_get_status(self, engine):
        # First create a mission
        await engine.run_sync("Test", "default")

        # Get status
        missions = await engine.list_missions("default", limit=1)
        assert len(missions) > 0

        mission_id = missions[0]["id"]
        status = await engine.get_status(mission_id, "default")
        assert status["id"] == mission_id
        assert status["status"] in ["completed", "failed"]

    @pytest.mark.asyncio
    async def test_cancel(self, engine):
        result = await engine.run_sync("Test", "default")
        missions = await engine.list_missions("default", limit=1)
        mission_id = missions[0]["id"]

        await engine.cancel(mission_id, "default")
        # Status should be updated
