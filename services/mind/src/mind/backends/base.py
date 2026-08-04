"""Vector / graph backend interface for mind."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class VectorBackend(ABC):
    """Portable interface for node upsert/search/delete."""

    @abstractmethod
    async def upsert(self, node: Dict[str, Any]) -> str:
        """Insert or update a node; return node id."""

    @abstractmethod
    async def search(
        self,
        query_embedding: List[float],
        workspace_id: str,
        *,
        filters: Optional[Dict[str, str]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Nearest-neighbor search scoped to workspace."""

    @abstractmethod
    async def delete(self, node_id: str, workspace_id: str) -> bool:
        """Delete a node if it belongs to workspace."""

    @abstractmethod
    async def get(self, node_id: str, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single node."""
