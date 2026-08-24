"""Client for the mind service.

The router owns dispatch. Mind owns tenant-scoped knowledge. When a profile
asks for retrieval, the router queries Mind and injects context before the
provider call. That is the intelligent-routing product, not a sidecar.

Statuses are distinct on purpose:

- ``used`` — context was attached
- ``empty`` — Mind answered; the corpus had nothing (allowed)
- ``unavailable`` — Mind down, timeout, or error. Production fails closed.
  Local Compose may continue and must label the miss.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

STATUS_USED = "used"
STATUS_EMPTY = "empty"
STATUS_UNAVAILABLE = "unavailable"

DEFAULT_CONTEXT_HEADER = (
    "Use the following retrieved context to answer. "
    "If it does not contain the answer, say so rather than guessing.\n\n"
)


@dataclass
class RetrievalOutcome:
    status: str
    hits: List[Dict[str, Any]] = field(default_factory=list)
    context: str = ""

    @property
    def used(self) -> bool:
        return self.status == STATUS_USED


class MindClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        *,
        timeout: float = 3.0,
        max_context_chars: int = 6000,
    ):
        self.base_url = (
            base_url or os.environ.get("MIND_URL", "http://localhost:9081")
        ).rstrip("/")
        self.timeout = timeout
        self.max_context_chars = max_context_chars
        self.client: Optional[httpx.AsyncClient] = None
        self.enabled = True

    async def init(self):
        """Create the client and report reachability.

        Startup reachability is logged but not latched. Services come up in
        arbitrary order, and a mind that is slow to start should not disable
        retrieval for the lifetime of the router process.
        """
        self.client = httpx.AsyncClient(timeout=self.timeout)
        try:
            resp = await self.client.get(f"{self.base_url}/health", timeout=2)
            if resp.status_code == 200:
                print("[router] mind client connected")
                return
        except Exception:
            pass
        print(
            f"[router] mind not reachable at {self.base_url} yet; "
            "retrieval will retry per request"
        )

    async def close(self):
        if self.client:
            await self.client.aclose()
            self.client = None

    async def query(
        self, query: str, workspace_id: str, top_k: int = 4, correlation_id: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        if not self.enabled or not self.client or not query.strip():
            return None
        headers = {"X-Workspace-ID": workspace_id}
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        # The router retrieves for every tenant, so it authenticates as a
        # service and names the real caller in the header.
        service_key = os.environ.get("KUBEMIND_SERVICE_KEY")
        if service_key:
            headers["X-API-Key"] = service_key
        try:
            resp = await self.client.post(
                f"{self.base_url}/v1/query",
                json={"query": query, "top_k": top_k},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[router] retrieval unavailable: {e}")
            return None

        results = data.get("results") or data.get("nodes") or []
        return results if isinstance(results, list) else []

    async def retrieve(
        self, query: str, workspace_id: str, top_k: int = 4, correlation_id: Optional[str] = None
    ) -> RetrievalOutcome:
        if not self.enabled or not self.client or not query.strip():
            return RetrievalOutcome(STATUS_UNAVAILABLE)
        hits = await self.query(query, workspace_id, top_k=top_k, correlation_id=correlation_id)
        if hits is None:
            return RetrievalOutcome(STATUS_UNAVAILABLE)
        context = self.format_context(hits)
        if not context:
            return RetrievalOutcome(STATUS_EMPTY, hits=hits)
        return RetrievalOutcome(STATUS_USED, hits=hits, context=context)

    def format_context(self, results: List[Dict[str, Any]]) -> str:
        if not results:
            return ""
        chunks: List[str] = []
        used = 0
        for idx, item in enumerate(results, start=1):
            content = (
                item.get("content")
                or item.get("text")
                or item.get("chunk")
                or ""
            )
            if not content:
                continue
            source = item.get("source") or item.get("id") or f"result {idx}"
            block = f"[{idx}] ({source})\n{content}".strip()
            if used + len(block) > self.max_context_chars:
                block = block[: max(0, self.max_context_chars - used)]
                if block:
                    chunks.append(block)
                break
            chunks.append(block)
            used += len(block)
        if not chunks:
            return ""
        return DEFAULT_CONTEXT_HEADER + "\n\n".join(chunks)
