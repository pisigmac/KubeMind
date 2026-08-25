import os
import httpx
from typing import List, Dict, Optional

class MemoryManager:
    def __init__(self):
        try:
            from kubemind_config import get_mind_url
            self.mind_url = get_mind_url()
        except ImportError:
            self.mind_url = os.environ.get("MIND_URL", "http://localhost:9081")
        self.client: Optional[httpx.AsyncClient] = None
        self.is_ready = False
        self.retention_turns = int(os.environ.get("MEMORY_RETENTION_TURNS", "10"))

    async def init(self):
        self.client = httpx.AsyncClient(timeout=30)
        self.is_ready = True

    async def read(self, workspace_id: str, agent_id: str = "default") -> List[Dict]:
        if not self.client:
            return []

        try:
            resp = await self.client.post(
                f"{self.mind_url}/v1/query",
                headers={
                    "X-Workspace-ID": workspace_id,
                    "Authorization": "Bearer tricore-local-dev-key",
                },
                json={
                    "query": f"agent_memory agent_id:{agent_id}",
                    "filters": {"type": "agent_memory"},
                    "top_k": self.retention_turns,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", [])
        except Exception:
            return []

    async def write(self, workspace_id: str, key: str, value: str, agent_id: str = "default") -> str:
        if not self.client:
            return ""

        try:
            resp = await self.client.post(
                f"{self.mind_url}/v1/ingest",
                headers={
                    "X-Workspace-ID": workspace_id,
                    "Authorization": "Bearer tricore-local-dev-key",
                },
                json={
                    "source": f"memory://{agent_id}/{key}",
                    "type": "agent_memory",
                },
            )
            resp.raise_for_status()
            return resp.json().get("node_ids", [""])[0]
        except Exception:
            return ""

    async def ingest_conversation(self, workspace_id: str, mission_id: str, turn_index: int, content: str, agent_id: str = "default") -> str:
        if not self.client:
            return ""

        try:
            resp = await self.client.post(
                f"{self.mind_url}/v1/ingest",
                headers={
                    "X-Workspace-ID": workspace_id,
                    "Authorization": "Bearer tricore-local-dev-key",
                },
                json={
                    "source": f"conversation://{mission_id}/{turn_index}",
                    "type": "conversation",
                },
            )
            resp.raise_for_status()
            return resp.json().get("node_ids", [""])[0]
        except Exception:
            return ""

    async def close(self):
        if self.client:
            await self.client.aclose()
