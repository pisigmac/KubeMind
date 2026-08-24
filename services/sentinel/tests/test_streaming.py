import pytest
from unittest.mock import AsyncMock

from sentinel.streaming import ConnectionManager


@pytest.fixture
def mock_ws():
    """A stand-in WebSocket.

    The previous inline mock defined `accept` as a zero-argument lambda on a
    class, so the bound call passed `self` and raised TypeError before any
    assertion ran. Its methods also have to be awaitable.
    """
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


class TestConnectionManager:
    @pytest.fixture
    def manager(self):
        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_connect_disconnect(self, manager, mock_ws):
        await manager.connect(mock_ws)
        assert manager.get_connection_count() == 1

        manager.disconnect(mock_ws)
        assert manager.get_connection_count() == 0

    @pytest.mark.asyncio
    async def test_connect_accepts_the_handshake(self, manager, mock_ws):
        await manager.connect(mock_ws)
        mock_ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_subscribe(self, manager, mock_ws):
        await manager.connect(mock_ws)
        await manager.subscribe(mock_ws, "ws1")
        assert "ws1" in manager.workspace_subscriptions

    @pytest.mark.asyncio
    async def test_send_to_workspace_reaches_subscribers(self, manager, mock_ws):
        await manager.connect(mock_ws)
        await manager.subscribe(mock_ws, "ws1")
        await manager.send_to_workspace("ws1", '{"type":"span"}')
        mock_ws.send_text.assert_awaited_with('{"type":"span"}')

    @pytest.mark.asyncio
    async def test_send_to_workspace_skips_other_tenants(self, manager, mock_ws):
        await manager.connect(mock_ws)
        await manager.subscribe(mock_ws, "ws1")
        mock_ws.send_text.reset_mock()
        await manager.send_to_workspace("ws2", '{"type":"span"}')
        mock_ws.send_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_disconnect_clears_subscriptions(self, manager, mock_ws):
        await manager.connect(mock_ws)
        await manager.subscribe(mock_ws, "ws1")
        manager.disconnect(mock_ws)
        assert mock_ws not in manager.workspace_subscriptions.get("ws1", set())
