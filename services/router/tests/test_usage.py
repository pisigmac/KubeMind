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
