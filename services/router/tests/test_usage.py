import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from router.usage import UsageTracker

class TestUsageTracker:
    @pytest.mark.asyncio
    async def test_record_and_summary(self):
        tracker = UsageTracker()
        tracker.session_maker = MagicMock()
        session = AsyncMock()
        tracker.session_maker.return_value.__aenter__ = AsyncMock(return_value=session)
        tracker.session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        await tracker.record("ws-1", "ollama", "llama3.1", {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
        session.add.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_summary_no_data(self):
        tracker = UsageTracker()
        tracker.session_maker = None
        result = await tracker.get_summary("ws-1")
        assert result["total_requests"] == 0
        assert result["estimated_cost"] == 0.0

class TestOrgLevelRollup:
    """Verify cross-workspace aggregation for org-level reporting."""

    @pytest.mark.asyncio
    async def test_org_analytics_aggregates_all_workspaces(self):
        import os
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
        usage_tracker = UsageTracker()
        await usage_tracker.init()
        try:
            from router.usage import UsageRecord
            async with usage_tracker.session_maker() as session:
                session.add(UsageRecord(workspace_id="ws-a", provider="openai", model="gpt-4", requests=1, prompt_tokens=100, completion_tokens=50, total_tokens=150, estimated_cost=0.005))
                session.add(UsageRecord(workspace_id="ws-b", provider="anthropic", model="claude-3", requests=1, prompt_tokens=200, completion_tokens=100, total_tokens=300, estimated_cost=0.012))
                await session.commit()

            result = await usage_tracker.get_org_analytics(window_hours=24)
            assert result["total_spend"] == pytest.approx(0.017)
            assert result["total_requests"] == 2
            assert len(result["workspace_breakdown"]) == 2
        finally:
            await usage_tracker.close()

    @pytest.mark.asyncio
    async def test_org_analytics_with_no_data(self):
        import os
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
        usage_tracker = UsageTracker()
        await usage_tracker.init()
        try:
            result = await usage_tracker.get_org_analytics(window_hours=24)
            assert result["total_spend"] == 0
            assert result["total_requests"] == 0
        finally:
            await usage_tracker.close()
