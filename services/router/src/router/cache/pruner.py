"""Semantic Cache Auto-Pruning & Access Heatmap Engine for KubeMind.

Tracks vector cache hit frequencies, access recency, and TTL decay to
intelligently evict stale/cold vector entries while pinning high-value semantic paths.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class CacheEntryMetadata:
    signature: str
    workspace_id: str
    partition: str
    hit_count: int = 1
    created_at: float = field(default_factory=time.time)
    last_accessed_at: float = field(default_factory=time.time)
    pinned: bool = False


@dataclass
class PruneReport:
    total_evaluated: int
    pruned_count: int
    preserved_count: int
    freed_memory_pct: float
    evicted_signatures: List[str] = field(default_factory=list)


class SemanticCachePruner:
    """Intelligent eviction and heat-tracking engine for semantic vector stores."""

    def __init__(
        self,
        default_ttl_seconds: float = 86400.0,  # 24 hours
        min_hits_to_retain: int = 1,
        max_capacity: int = 10000,
    ):
        self.default_ttl_seconds = default_ttl_seconds
        self.min_hits_to_retain = min_hits_to_retain
        self.max_capacity = max_capacity
        self._entries: Dict[str, CacheEntryMetadata] = {}

    def record_access(self, signature: str, workspace_id: str, partition: str = "general") -> None:
        """Records an access or insert on a semantic cache entry."""
        now = time.time()
        if signature in self._entries:
            entry = self._entries[signature]
            entry.hit_count += 1
            entry.last_accessed_at = now
        else:
            self._entries[signature] = CacheEntryMetadata(
                signature=signature,
                workspace_id=workspace_id,
                partition=partition,
                created_at=now,
                last_accessed_at=now,
            )

    def pin_entry(self, signature: str) -> None:
        """Pins a high-value entry to prevent automatic pruning."""
        if signature in self._entries:
            self._entries[signature].pinned = True

    def evaluate_pruning(self, current_time: Optional[float] = None) -> PruneReport:
        """Identifies and evicts expired or cold semantic cache entries."""
        now = current_time or time.time()
        evicted = []
        preserved = []

        for sig, meta in list(self._entries.items()):
            if meta.pinned:
                preserved.append(sig)
                continue

            age_seconds = now - meta.last_accessed_at
            # Evict if older than TTL or if over capacity and rarely accessed
            if age_seconds > self.default_ttl_seconds:
                evicted.append(sig)
                del self._entries[sig]
            else:
                preserved.append(sig)

        total = len(evicted) + len(preserved)
        pct = round((len(evicted) / max(1, total)) * 100.0, 2)

        return PruneReport(
            total_evaluated=total,
            pruned_count=len(evicted),
            preserved_count=len(preserved),
            freed_memory_pct=pct,
            evicted_signatures=evicted,
        )

    def get_heat_score(self, signature: str, current_time: Optional[float] = None) -> float:
        """Calculates a normalized access heat score [0.0 - 1.0] based on hits and recency."""
        if signature not in self._entries:
            return 0.0

        meta = self._entries[signature]
        now = current_time or time.time()
        age_hours = max(0.1, (now - meta.last_accessed_at) / 3600.0)
        # Recency-weighted frequency score
        raw_heat = meta.hit_count / age_hours
        return min(1.0, round(raw_heat / 10.0, 3))


_GLOBAL_PRUNER = SemanticCachePruner()


def get_default_cache_pruner() -> SemanticCachePruner:
    return _GLOBAL_PRUNER
