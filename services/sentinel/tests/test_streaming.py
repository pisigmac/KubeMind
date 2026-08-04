import pytest
from sentinel.streaming import ConnectionManager

class TestConnectionManager:
    @pytest.fixture
    def manager(self):
        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_connect_disconnect(self, manager):
        mock_ws = type("MockWS", (), {
            "accept": lambda: None,
            "send_text": lambda x: None,
        })()
        await manager.connect(mock_ws)
        assert manager.get_connection_count() == 1

        manager.disconnect(mock_ws)
        assert manager.get_connection_count() == 0

    @pytest.mark.asyncio
    async def test_subscribe(self, manager):
        mock_ws = type("MockWS", (), {
            "accept": lambda: None,
            "send_text": lambda x: None,
        })()
        await manager.connect(mock_ws)
        await manager.subscribe(mock_ws, "ws1")
        assert "ws1" in manager.workspace_subscriptions
