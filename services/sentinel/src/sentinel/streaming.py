from typing import Set
from fastapi import WebSocket
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.workspace_subscriptions: dict = {}  # workspace_id -> set of websockets

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        # Remove from workspace subscriptions
        for ws_set in self.workspace_subscriptions.values():
            ws_set.discard(websocket)

    async def subscribe(self, websocket: WebSocket, workspace_id: str):
        if workspace_id not in self.workspace_subscriptions:
            self.workspace_subscriptions[workspace_id] = set()
        self.workspace_subscriptions[workspace_id].add(websocket)
        await websocket.send_text(json.dumps({"type": "subscribed", "workspace_id": workspace_id}))

    async def broadcast(self, message: str):
        disconnected = set()
        for conn in self.active_connections:
            try:
                await conn.send_text(message)
            except Exception:
                disconnected.add(conn)

        for conn in disconnected:
            self.disconnect(conn)

    async def send_to_workspace(self, workspace_id: str, message: str):
        if workspace_id not in self.workspace_subscriptions:
            return

        disconnected = set()
        for conn in self.workspace_subscriptions[workspace_id]:
            try:
                await conn.send_text(message)
            except Exception:
                disconnected.add(conn)

        for conn in disconnected:
            self.disconnect(conn)
            self.workspace_subscriptions[workspace_id].discard(conn)

    def get_connection_count(self) -> int:
        return len(self.active_connections)
