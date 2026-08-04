"""Client for the mind service.

Lets the router *assemble* a request rather than just forward it: when the
classifier says a prompt is asking about workspace knowledge, the router
retrieves that knowledge and injects it before dispatch. A gateway that does
not own a memory service cannot do this.

Retrieval is best-effort. If mind is slow or down the request proceeds without
context, because a degraded answer beats a failed one.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

DEFAULT_CONTEXT_HEADER = (
    "Use the following retrieved context to answer. "
    "If it does not contain the answer, say so rather than guessing.\n\n"
)


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
        self, query: str, workspace_id: str, top_k: int = 4
    ) -> List[Dict[str, Any]]:
        if not self.enabled or not self.client or not query.strip():
            return []
        try:
            resp = await self.client.post(
                f"{self.base_url}/v1/query",
                json={"query": query, "top_k": top_k},
                headers={"X-Workspace-ID": workspace_id},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[router] retrieval failed: {e}")
            return []

        results = data.get("results") or data.get("nodes") or []
        return results if isinstance(results, list) else []

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
