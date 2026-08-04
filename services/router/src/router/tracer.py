import os
import httpx
from typing import Dict, Any, Optional


class TracerClient:
    def __init__(self):
        self.sentinel_url = os.environ.get(
            "SENTINEL_URL",
            os.environ.get("TRACER_URL", "http://localhost:9083"),
        )
        self.client: Optional[httpx.AsyncClient] = None
        self.enabled = True

    async def init(self):
        try:
            self.client = httpx.AsyncClient(timeout=5)
            resp = await self.client.get(f"{self.sentinel_url}/health", timeout=2)
            if resp.status_code == 200:
                print("[router] Tracer client connected")
            else:
                self.enabled = False
        except Exception:
            self.enabled = False
            print("[router] Tracer unavailable, running without tracing")

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

    async def close(self):
        if self.client:
            await self.client.aclose()
