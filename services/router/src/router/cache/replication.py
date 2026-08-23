"""Cross-Cluster Distributed Semantic Cache Replication Engine for KubeMind.

Replicates high-confidence semantic vector entries across multi-region edge gateways.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import httpx


@dataclass
class ReplicatedCacheEntry:
    workspace_id: str
    signature: str
    partition: str
    model: str
    intent: str
    prompt_preview: str
    embedding: List[float]
    response: Dict[str, Any]
    origin_region: str
    created_at: float = field(default_factory=time.time)


class DistributedCacheReplicator:
    """Replicates semantic vector cache records to remote peer clusters."""

    def __init__(self, current_region: str = "us-east-1", peer_endpoints: Optional[List[str]] = None):
        self.current_region = current_region
        self.peer_endpoints = peer_endpoints or []
        self._outbound_queue: List[ReplicatedCacheEntry] = []

    def register_peer(self, endpoint: str) -> None:
        """Register a remote KubeMind cluster endpoint for cross-region replication."""
        if endpoint and endpoint not in self.peer_endpoints:
            self.peer_endpoints.append(endpoint.rstrip("/"))

    def queue_replication(
        self,
        workspace_id: str,
        signature: str,
        partition: str,
        model: str,
        intent: str,
        prompt_preview: str,
        embedding: List[float],
        response: Dict[str, Any],
    ) -> None:
        """Queue a local cache hit/store entry for background replication."""
        entry = ReplicatedCacheEntry(
            workspace_id=workspace_id,
            signature=signature,
            partition=partition,
            model=model,
            intent=intent,
            prompt_preview=prompt_preview,
            embedding=embedding,
            response=response,
            origin_region=self.current_region,
        )
        self._outbound_queue.append(entry)

    async def flush_replication_queue(self, timeout: float = 3.0) -> List[Dict[str, Any]]:
        """Push queued replication entries to remote peer clusters."""
        if not self._outbound_queue or not self.peer_endpoints:
            return []

        entries_to_send = list(self._outbound_queue)
        self._outbound_queue.clear()
        results = []

        payload = {
            "origin_region": self.current_region,
            "entries_count": len(entries_to_send),
            "entries": [
                {
                    "workspace_id": e.workspace_id,
                    "signature": e.signature,
                    "partition": e.partition,
                    "model": e.model,
                    "intent": e.intent,
                    "prompt_preview": e.prompt_preview,
                    "response": e.response,
                }
                for e in entries_to_send
            ],
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            for peer in self.peer_endpoints:
                url = f"{peer}/v1/cache/replicate"
                try:
                    resp = await client.post(url, json=payload)
                    results.append({
                        "peer": peer,
                        "status_code": resp.status_code,
                        "success": 200 <= resp.status_code < 300,
                    })
                except Exception as e:
                    results.append({
                        "peer": peer,
                        "status_code": 0,
                        "success": False,
                        "error": str(e),
                    })

        return results


_GLOBAL_REPLICATOR = DistributedCacheReplicator()


def get_default_cache_replicator() -> DistributedCacheReplicator:
    return _GLOBAL_REPLICATOR
