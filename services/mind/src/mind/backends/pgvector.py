"""Default backend: KnowledgeStore with optional pgvector HNSW."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mind.backends.base import VectorBackend
from mind.storage import KnowledgeStore


class PgVectorBackend(VectorBackend):
    def __init__(self, store: KnowledgeStore):
        self.store = store

    async def upsert(self, node: Dict[str, Any]) -> str:
        return await self.store.save(node)

    async def search(
        self,
        query_embedding: List[float],
        workspace_id: str,
        *,
        filters: Optional[Dict[str, str]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        return await self.store.search_by_vector(
            query_embedding, workspace_id, filters=filters, limit=limit
        )

    async def delete(self, node_id: str, workspace_id: str) -> bool:
        # Minimal: not yet exposed on KnowledgeStore; return False
        return False

    async def get(self, node_id: str, workspace_id: str) -> Optional[Dict[str, Any]]:
        return await self.store.get(node_id, workspace_id)
