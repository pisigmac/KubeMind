"""Milvus backend — not implemented (Phase 2 stretch)."""

from typing import Any, Dict, List, Optional

from mind.backends.base import VectorBackend


class MilvusBackend(VectorBackend):
    async def upsert(self, node: Dict[str, Any]) -> str:
        raise NotImplementedError("Milvus backend is not implemented yet")

    async def search(
        self,
        query_embedding: List[float],
        workspace_id: str,
        *,
        filters: Optional[Dict[str, str]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError("Milvus backend is not implemented yet")

    async def delete(self, node_id: str, workspace_id: str) -> bool:
        raise NotImplementedError("Milvus backend is not implemented yet")

    async def get(self, node_id: str, workspace_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("Milvus backend is not implemented yet")
