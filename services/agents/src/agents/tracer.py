import os
import httpx
from typing import Dict, Any, Optional
from datetime import datetime

class TracerClient:
    def __init__(self, service_name: str = "unknown"):
        try:
            from kubemind_config import get_sentinel_url
            self.sentinel_url = get_sentinel_url()
        except ImportError:
            self.sentinel_url = os.environ.get("SENTINEL_URL", "http://localhost:9083")
        self.service_name = service_name
        self.client: Optional[httpx.AsyncClient] = None
        self.enabled = True
        self._buffer: list = []

    async def init(self):
        try:
            self.client = httpx.AsyncClient(timeout=5)
            resp = await self.client.get(f"{self.sentinel_url}/health", timeout=2)
            if resp.status_code == 200:
                print(f"[{self.service_name}] Tracer client connected")
            else:
                self.enabled = False
        except Exception:
            self.enabled = False

    async def log_span(self, span: Dict[str, Any]):
        if not self.enabled or not self.client:
            return
        try:
            await self.client.post(
                f"{self.sentinel_url}/v1/spans",
                json=span,
                timeout=3,
            )
        except Exception:
            pass

    async def log_request(self, workspace_id: str, operation: str, duration_ms: float, status: str = "ok", attributes: Dict = None):
        await self.log_span({
            "trace_id": f"req-{workspace_id}-{datetime.utcnow().timestamp()}",
            "span_id": f"req-{datetime.utcnow().timestamp()}",
            "workspace_id": workspace_id,
            "service": self.service_name,
            "operation": operation,
            "start_time": datetime.utcnow().isoformat(),
            "status": status,
            "attributes": {"duration_ms": duration_ms, **(attributes or {})},
        })

    async def log_tool_call(self, workspace_id: str, tool: str, duration_ms: float, status: str = "ok", attributes: Dict = None):
        await self.log_span({
            "trace_id": f"tool-{workspace_id}-{datetime.utcnow().timestamp()}",
            "span_id": f"tool-{datetime.utcnow().timestamp()}",
            "workspace_id": workspace_id,
            "service": self.service_name,
            "operation": "tool_call",
            "start_time": datetime.utcnow().isoformat(),
            "status": status,
            "attributes": {"tool": tool, "duration_ms": duration_ms, **(attributes or {})},
        })

    async def close(self):
        if self.client:
            await self.client.aclose()
