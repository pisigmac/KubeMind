import os
import httpx
import time
from typing import Dict, Any, Optional
from datetime import datetime

class TracerClient:
    """Client for emitting traces to the sentinel service.

    Usage in any service:
        sentinel = TracerClient()
        await sentinel.init()
        await sentinel.log_span({...})
    """

    def __init__(self, service_name: str = "unknown"):
        self.sentinel_url = os.environ.get("SENTINEL_URL", "http://localhost:9083")
        self.service_name = service_name
        self.client: Optional[httpx.AsyncClient] = None
        self.enabled = True
        self._buffer: list = []
        self._buffer_size = int(os.environ.get("TRACER_BUFFER_SIZE", "100"))
        self._flush_interval = float(os.environ.get("TRACER_FLUSH_INTERVAL", "5.0"))

    async def init(self):
        try:
            self.client = httpx.AsyncClient(
                timeout=5,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
            # Quick health check
            resp = await self.client.get(f"{self.sentinel_url}/health", timeout=2)
            if resp.status_code == 200:
                print(f"[{self.service_name}] Tracer client connected to {self.sentinel_url}")
            else:
                self.enabled = False
        except Exception:
            self.enabled = False
            print(f"[{self.service_name}] Tracer unavailable at {self.sentinel_url}, running without tracing")

    async def log_span(self, span: Dict[str, Any]):
        if not self.enabled or not self.client:
            return

        # Enrich span with service name if not provided
        if "service" not in span:
            span["service"] = self.service_name
        if "span_id" not in span:
            span["span_id"] = f"{self.service_name}-{time.time()}"
        if "trace_id" not in span:
            span["trace_id"] = span["span_id"]
        if "start_time" not in span:
            span["start_time"] = datetime.utcnow().isoformat()

        self._buffer.append(span)

        if len(self._buffer) >= self._buffer_size:
            await self._flush()

    async def log_llm_call(self, workspace_id: str, provider: str, model: str, 
                           prompt_tokens: int, completion_tokens: int, duration_ms: float,
                           status: str = "ok", attributes: Dict = None):
        await self.log_span({
            "trace_id": f"llm-{workspace_id}-{time.time()}",
            "span_id": f"llm-{time.time()}",
            "workspace_id": workspace_id,
            "service": self.service_name,
            "operation": "llm_call",
            "start_time": datetime.utcnow().isoformat(),
            "status": status,
            "attributes": {
                "provider": provider,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "duration_ms": duration_ms,
                **(attributes or {}),
            },
        })

    async def log_tool_call(self, workspace_id: str, tool: str, duration_ms: float,
                            status: str = "ok", attributes: Dict = None):
        await self.log_span({
            "trace_id": f"tool-{workspace_id}-{time.time()}",
            "span_id": f"tool-{time.time()}",
            "workspace_id": workspace_id,
            "service": self.service_name,
            "operation": "tool_call",
            "start_time": datetime.utcnow().isoformat(),
            "status": status,
            "attributes": {
                "tool": tool,
                "duration_ms": duration_ms,
                **(attributes or {}),
            },
        })

    async def log_request(self, workspace_id: str, operation: str, duration_ms: float,
                          status: str = "ok", attributes: Dict = None):
        await self.log_span({
            "trace_id": f"req-{workspace_id}-{time.time()}",
            "span_id": f"req-{time.time()}",
            "workspace_id": workspace_id,
            "service": self.service_name,
            "operation": operation,
            "start_time": datetime.utcnow().isoformat(),
            "status": status,
            "attributes": {
                "duration_ms": duration_ms,
                **(attributes or {}),
            },
        })

    async def _flush(self):
        if not self._buffer or not self.client:
            return

        spans = self._buffer[:]
        self._buffer = []

        # Services emit spans for every tenant, so they authenticate as a
        # service and name the real workspace per span.
        service_key = os.environ.get("KUBEMIND_SERVICE_KEY")

        try:
            for span in spans:
                headers = {}
                if span.get("workspace_id"):
                    headers["X-Workspace-ID"] = span["workspace_id"]
                if service_key:
                    headers["X-API-Key"] = service_key
                await self.client.post(
                    f"{self.sentinel_url}/v1/spans",
                    json=span,
                    headers=headers,
                    timeout=3,
                )
        except Exception:
            # Silently fail — tracing should never break the main flow
            pass

    async def close(self):
        await self._flush()
        if self.client:
            await self.client.aclose()
