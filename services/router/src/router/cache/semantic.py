"""Semantic prompt cache backed by Redis + in-process cosine search."""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
import redis.asyncio as redis


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def cosine_distance(a: List[float], b: List[float]) -> float:
    return 1.0 - cosine_similarity(a, b)


def signature(model: str, system_prompt: str = "", temperature: float = 0.0) -> str:
    """Identity of everything except the prompt text.

    Matching on embedding distance alone let a `llama3.1` answer satisfy a
    `gpt-4o` request. Entries only match when this signature is identical.
    """
    payload = json.dumps(
        {"model": model or "", "system": system_prompt or "", "temp": round(float(temperature or 0.0), 3)},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class SemanticCache:
    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        *,
        enabled: bool = True,
        embedding_model: str = "nomic-embed-text",
        distance_threshold: float = 0.05,
        max_entries: int = 10000,
        scan_limit: int = 2000,
        ttl_seconds: int = 300,
        ollama_base_url: Optional[str] = None,
        partition_by_intent: bool = True,
        embedding_prefix: str = "search_query: ",
        backend: str = "redis",
        pgvector_store: Any = None,
    ):
        self.client = redis_client
        self.enabled = enabled
        self.embedding_model = embedding_model
        self.distance_threshold = distance_threshold
        self.max_entries = max_entries
        self.scan_limit = scan_limit
        self.ttl_seconds = ttl_seconds
        self.partition_by_intent = partition_by_intent
        # nomic-embed-text is trained with task prefixes and is measurably
        # worse without one. One vector serves two tasks here -- symmetric
        # cache lookup and classification -- so a single prefix is a
        # compromise, taken knowingly to avoid embedding twice.
        #
        # `search_query:` is chosen because both sides of both comparisons are
        # short user-style text. What actually matters is that the *same*
        # prefix is applied to intent examples at index time, to prompts at
        # query time, and to cache entries on store and lookup. A mismatch
        # there degrades quality silently, with no error anywhere.
        self.embedding_prefix = embedding_prefix
        self.backend = backend
        self.pgvector = pgvector_store
        self.ollama_base_url = (
            ollama_base_url
            or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        ).rstrip("/")
        self._http: Optional[httpx.AsyncClient] = None
        self.is_ready = False

    def bind_redis(self, client: Optional[redis.Redis]):
        self.client = client
        if self.backend == "pgvector":
            self.is_ready = bool(self.pgvector and self.pgvector.is_ready) and self.enabled
        else:
            self.is_ready = bool(client) and self.enabled

    async def _http_client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    async def close(self):
        if self._http:
            await self._http.aclose()
            self._http = None
        if self.pgvector:
            self.pgvector.close()

    @property
    def embedding_namespace(self) -> str:
        """Short hash of everything that changes what a vector means.

        Vectors from different models or prefixes are not comparable, so they
        must not share a key. Rolling the namespace retires stale entries
        naturally via TTL instead of serving nonsense distances after a config
        change.
        """
        raw = f"{self.embedding_model}|{self.embedding_prefix}"
        return hashlib.sha256(raw.encode()).hexdigest()[:8]

    def _list_key(self, workspace_id: str, partition: Optional[str] = None) -> str:
        base = f"km:sem:{self.embedding_namespace}:{workspace_id}"
        if self.partition_by_intent and partition:
            return f"{base}:{partition}"
        return base

    async def embed(self, text: str) -> Optional[List[float]]:
        if not text or not text.strip():
            return None
        try:
            client = await self._http_client()
            resp = await client.post(
                f"{self.ollama_base_url}/api/embeddings",
                json={
                    "model": self.embedding_model,
                    "prompt": f"{self.embedding_prefix}{text[:8000]}",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            emb = data.get("embedding")
            if not emb:
                return None
            return [float(x) for x in emb]
        except Exception as e:
            print(f"[router] semantic embed failed: {e}")
            return None

    async def lookup(
        self,
        workspace_id: str,
        embedding: List[float],
        *,
        sig: Optional[str] = None,
        partition: Optional[str] = None,
        distance_threshold: Optional[float] = None,
    ) -> Optional[Tuple[Dict[str, Any], float, Dict[str, Any]]]:
        """Return (response_payload, distance, entry_meta) on hit."""
        if not self.enabled or not embedding:
            return None

        threshold = (
            distance_threshold
            if distance_threshold is not None
            else self.distance_threshold
        )

        if self.backend == "pgvector" and self.pgvector and self.pgvector.is_ready:
            return self.pgvector.lookup(
                workspace_id,
                embedding,
                sig=sig,
                partition=partition if self.partition_by_intent else None,
                distance_threshold=threshold,
            )

        if not self.client:
            return None

        keys = [self._list_key(workspace_id, partition)]
        # A low-confidence request reads the shared bucket too, so prompts that
        # sit near a decision boundary can still hit entries written under a
        # confident classification.
        shared = self._list_key(workspace_id)
        if shared not in keys:
            keys.append(shared)

        best: Optional[Dict[str, Any]] = None
        best_dist = 1.0
        for key in keys:
            try:
                raw_entries = await self.client.lrange(key, 0, self.scan_limit - 1)
            except Exception:
                continue
            for raw in raw_entries or []:
                try:
                    entry = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    continue
                if sig is not None and entry.get("signature") not in (None, sig):
                    continue
                stored = entry.get("embedding")
                if not stored:
                    continue
                dist = cosine_distance(embedding, stored)
                if dist < best_dist:
                    best_dist = dist
                    best = entry

        if best is None or best_dist > threshold:
            return None
        response = best.get("response")
        if not isinstance(response, dict):
            return None
        meta = {
            "intent": best.get("intent"),
            "model": best.get("model"),
            "signature": best.get("signature"),
        }
        return response, best_dist, meta

    async def store(
        self,
        workspace_id: str,
        embedding: List[float],
        response: Dict[str, Any],
        *,
        model: str,
        prompt_preview: str,
        intent: Optional[str] = None,
        sig: Optional[str] = None,
        partition: Optional[str] = None,
    ) -> None:
        if not self.enabled or not embedding:
            return

        if self.backend == "pgvector" and self.pgvector and self.pgvector.is_ready:
            self.pgvector.store(
                workspace_id,
                embedding,
                response,
                model=model,
                prompt_preview=prompt_preview,
                intent=intent,
                sig=sig,
                partition=partition if self.partition_by_intent else None,
            )
            return

        if not self.client:
            return
        key = self._list_key(workspace_id, partition)
        # Avoid storing large recursive metadata
        payload = {
            k: v
            for k, v in response.items()
            if k
            not in (
                "cache_hit",
                "cache_type",
                "distance",
                "similarity",
                "latency_ms",
            )
        }
        entry = {
            "embedding": embedding,
            "response": payload,
            "model": model,
            "intent": intent,
            "signature": sig,
            "prompt_preview": prompt_preview[:200],
            "created_at": time.time(),
        }
        try:
            await self.client.lpush(key, json.dumps(entry))
            await self.client.ltrim(key, 0, self.max_entries - 1)
            await self.client.expire(key, self.ttl_seconds)
        except Exception as e:
            print(f"[router] semantic store failed: {e}")

    @classmethod
    def from_config(cls, config: Dict[str, Any], redis_client: Optional[redis.Redis] = None) -> "SemanticCache":
        cache_cfg = config.get("cache", {})
        sem = cache_cfg.get("semantic", {})
        backend = str(
            sem.get("backend")
            or cache_cfg.get("semantic_backend")
            or os.environ.get("KUBEMIND_SEMANTIC_CACHE_BACKEND", "redis")
        ).lower()

        pgvector_store = None
        if backend == "pgvector":
            from router.cache.pgvector import PgVectorStore

            pgvector_store = PgVectorStore(
                dims=int(sem.get("embedding_dims", 768)),
                ttl_seconds=int(cache_cfg.get("ttl_seconds", 300)),
                max_entries=int(sem.get("max_entries_per_workspace", 10000)),
            )
            if not pgvector_store.connect():
                # Degrade to Redis rather than running without a cache.
                backend = "redis"
                pgvector_store = None

        return cls(
            redis_client=redis_client,
            enabled=bool(sem.get("enabled", True)),
            embedding_model=sem.get("embedding_model", "nomic-embed-text"),
            distance_threshold=float(sem.get("distance_threshold", 0.05)),
            max_entries=int(sem.get("max_entries_per_workspace", 10000)),
            scan_limit=int(sem.get("scan_limit", 2000)),
            ttl_seconds=int(cache_cfg.get("ttl_seconds", 300)),
            partition_by_intent=bool(sem.get("partition_by_intent", True)),
            embedding_prefix=sem.get("embedding_prefix", "search_query: "),
            backend=backend,
            pgvector_store=pgvector_store,
        )
