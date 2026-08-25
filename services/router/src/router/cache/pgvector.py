"""pgvector-backed semantic cache store.

The Redis list implementation pulls up to 2000 JSON entries and scores cosine
distance in Python per request. That will not hold under real load and
undermines the low-latency claim. Postgres with pgvector does the nearest-
neighbour search in the database, scoped by workspace, signature and optional
intent partition.

The public surface matches what SemanticCache.lookup/store need, so the
router can swap backends without changing the dispatch path.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


DDL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS semantic_cache (
    id BIGSERIAL PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    partition TEXT NOT NULL DEFAULT '',
    signature TEXT NOT NULL DEFAULT '',
    model TEXT,
    intent TEXT,
    prompt_preview TEXT,
    embedding vector({dims}) NOT NULL,
    response JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_semantic_cache_lookup
    ON semantic_cache (workspace_id, partition, signature);

CREATE INDEX IF NOT EXISTS idx_semantic_cache_created
    ON semantic_cache (created_at);

CREATE INDEX IF NOT EXISTS idx_semantic_cache_hnsw
    ON semantic_cache USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
"""


class PgVectorStore:
    def __init__(
        self,
        database_url: Optional[str] = None,
        *,
        dims: int = 768,
        ttl_seconds: int = 300,
        max_entries: int = 10000,
    ):
        try:
            from kubemind_config import get_database_url
            self.database_url = database_url or get_database_url()
        except ImportError:
            self.database_url = database_url or os.environ.get(
                "DATABASE_URL",
                "postgresql://tricore:tricore@localhost:5432/tricore",
            )
        self.dims = dims
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.engine: Optional[Engine] = None
        self.is_ready = False

    def connect(self) -> bool:
        try:
            self.engine = create_engine(self.database_url, pool_pre_ping=True)
            with self.engine.begin() as conn:
                for stmt in DDL.format(dims=self.dims).split(";"):
                    sql = stmt.strip()
                    if sql:
                        try:
                            conn.execute(text(sql))
                        except Exception:
                            if "INDEX" in sql.upper():
                                continue
                            raise
            self.is_ready = True
            print(f"[router] pgvector semantic cache ready with HNSW indexing (dims={self.dims})")
            return True
        except Exception as e:
            print(f"[router] pgvector unavailable ({e}); semantic cache falls back")
            self.is_ready = False
            self.engine = None
            return False

    def close(self):
        if self.engine:
            self.engine.dispose()
            self.engine = None
            self.is_ready = False

    @staticmethod
    def _vec_literal(embedding: List[float]) -> str:
        return "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"

    def lookup(
        self,
        workspace_id: str,
        embedding: List[float],
        *,
        sig: Optional[str] = None,
        partition: Optional[str] = None,
        distance_threshold: float = 0.05,
    ) -> Optional[Tuple[Dict[str, Any], float, Dict[str, Any]]]:
        if not self.is_ready or not self.engine or not embedding:
            return None
        if len(embedding) != self.dims:
            # Dimension mismatch is a configuration error, not a miss. Refuse
            # rather than let Postgres raise on every request.
            return None

        partitions = [partition or ""]
        if partition:
            partitions.append("")  # shared bucket for low-confidence writers

        vec = self._vec_literal(embedding)
        try:
            with self.engine.connect() as conn:
                # Cosine distance operator <=> ; filter by signature in SQL so
                # a llama3.1 answer cannot satisfy a gpt-4o request.
                row = conn.execute(
                    text(
                        """
                        SELECT response, intent, model, signature,
                               (embedding <=> CAST(:vec AS vector)) AS distance
                        FROM semantic_cache
                        WHERE workspace_id = :ws
                          AND partition = ANY(:parts)
                          AND (:sig = '' OR signature = :sig OR signature = '')
                          AND created_at > NOW() - (:ttl * INTERVAL '1 second')
                        ORDER BY embedding <=> CAST(:vec AS vector)
                        LIMIT 1
                        """
                    ),
                    {
                        "vec": vec,
                        "ws": workspace_id,
                        "parts": partitions,
                        "sig": sig or "",
                        "ttl": self.ttl_seconds,
                    },
                ).mappings().first()
        except Exception as e:
            print(f"[router] pgvector lookup failed: {e}")
            return None

        if not row:
            return None
        distance = float(row["distance"])
        if distance > distance_threshold:
            return None
        response = row["response"]
        if isinstance(response, str):
            response = json.loads(response)
        if not isinstance(response, dict):
            return None
        meta = {
            "intent": row.get("intent"),
            "model": row.get("model"),
            "signature": row.get("signature"),
        }
        return response, distance, meta

    def store(
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
        if not self.is_ready or not self.engine or not embedding:
            return
        if len(embedding) != self.dims:
            return

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
        vec = self._vec_literal(embedding)
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO semantic_cache
                            (workspace_id, partition, signature, model, intent,
                             prompt_preview, embedding, response, created_at)
                        VALUES
                            (:ws, :part, :sig, :model, :intent,
                             :preview, CAST(:vec AS vector), CAST(:resp AS jsonb), NOW())
                        """
                    ),
                    {
                        "ws": workspace_id,
                        "part": partition or "",
                        "sig": sig or "",
                        "model": model,
                        "intent": intent,
                        "preview": (prompt_preview or "")[:200],
                        "vec": vec,
                        "resp": json.dumps(payload),
                    },
                )
                # Cap per-workspace volume the same way Redis LTRIM did.
                conn.execute(
                    text(
                        """
                        DELETE FROM semantic_cache
                        WHERE id IN (
                            SELECT id FROM semantic_cache
                            WHERE workspace_id = :ws
                            ORDER BY created_at DESC
                            OFFSET :keep
                        )
                        """
                    ),
                    {"ws": workspace_id, "keep": self.max_entries},
                )
        except Exception as e:
            print(f"[router] pgvector store failed: {e}")
