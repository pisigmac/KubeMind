import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.engine import AgentEngine

class TestAgentEngine:
    @pytest.fixture
    def engine(self, mock_tools, mock_planner, mock_memory):
        engine = AgentEngine(tools=mock_tools, planner=mock_planner, memory=mock_memory)
        engine.session_maker = MagicMock()
        session = AsyncMock()
        engine.session_maker.return_value.__aenter__ = AsyncMock(return_value=session)
        engine.session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        # Mock async ORM session helpers used across engine methods.
        mission_id = "test-mission-id"
        mission_mock = MagicMock()
        mission_mock.id = mission_id
        mission_mock.workspace_id = "default"
        mission_mock.prompt = "Test mission"
        mission_mock.status = "completed"
        mission_mock.output = "Result"
        mission_mock.error = None
        mission_mock.plan = {"todos": []}
        mission_mock.tool_calls = []
        mission_mock.tokens_used = 10
        mission_mock.duration_ms = 100
        mission_mock.created_at = None
        mission_mock.completed_at = None
        session.get.return_value = mission_mock

        execute_result = MagicMock()
        execute_result.scalars.return_value = [mission_mock]
        session.execute.return_value = execute_result

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
    async def test_run_sync_with_tools(self, engine, mock_tools, mock_planner):
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
