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
        """Create the client and report reachability.

        Reachability is not latched: services start in arbitrary order and a
        sentinel that is slow to come up should not disable the audit trail for
        the lifetime of the router process.
        """
        self.client = httpx.AsyncClient(timeout=5)
        try:
            resp = await self.client.get(f"{self.sentinel_url}/health", timeout=2)
            if resp.status_code == 200:
                print("[router] Tracer client connected")
                return
        except Exception:
            pass
        print(
            f"[router] sentinel not reachable at {self.sentinel_url} yet; "
            "spans will retry per request"
        )

    def _headers(self, workspace_id: Optional[str]) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if workspace_id:
            headers["X-Workspace-ID"] = workspace_id
        # The router writes spans for every tenant, so it authenticates as a
        # service and names the real workspace in the header.
        service_key = os.environ.get("KUBEMIND_SERVICE_KEY")
        if service_key:
            headers["X-API-Key"] = service_key
        return headers

    async def log_span(self, span: Dict[str, Any]):
        if not self.enabled or not self.client:
            return
        try:
            await self.client.post(
                f"{self.sentinel_url}/v1/spans",
                json=span,
                headers=self._headers(span.get("workspace_id")),
                timeout=3,
            )
        except Exception:
            pass

    async def close(self):
        if self.client:
            await self.client.aclose()
