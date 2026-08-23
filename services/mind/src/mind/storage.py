import os
import uuid
from typing import List, Dict, Optional, Any
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    select,
    text as sql_text,
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

Base = declarative_base()

EMBED_DIM = int(os.environ.get("EMBEDDING_DIMENSIONS", "768"))

# Optional pgvector type
try:
    from pgvector.sqlalchemy import Vector

    _HAS_PGVECTOR_LIB = True
except ImportError:
    Vector = None  # type: ignore
    _HAS_PGVECTOR_LIB = False


class NodeModel(Base):
    __tablename__ = "nodes"
    id = Column(String, primary_key=True)
    workspace_id = Column(String, index=True, nullable=False)
    type = Column(String, index=True, nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict)
    embedding = Column(JSON)  # portable JSON fallback
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Add vector column only if library present (actual DB extension checked at runtime)
if _HAS_PGVECTOR_LIB and Vector is not None:
    NodeModel.embedding_vec = Column(Vector(EMBED_DIM), nullable=True)  # type: ignore[attr-defined]


class LinkModel(Base):
    __tablename__ = "links"
    id = Column(String, primary_key=True)
    workspace_id = Column(String, index=True, nullable=False)
    source_id = Column(String, ForeignKey("nodes.id"), index=True, nullable=False)
    target_id = Column(String, ForeignKey("nodes.id"), index=True, nullable=False)
    link_type = Column(String, default="related")
    confidence = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class KnowledgeStore:
    def __init__(self):
        self.engine = None
        self.session_maker = None
        self.is_ready = False
        self.pgvector_enabled = False
        self.embed_dim = EMBED_DIM

    async def init(self, db_url: Optional[str] = None):
        db_url = db_url or os.environ.get(
            "DATABASE_URL", "postgresql://tricore:tricore@localhost:5432/tricore"
        )
        sqlite = db_url.startswith("sqlite")
        if sqlite:
            async_url = db_url if "+aiosqlite" in db_url else db_url.replace(
                "sqlite://", "sqlite+aiosqlite://", 1
            )
        else:
            async_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

        self.engine = create_async_engine(async_url, echo=False)

        async with self.engine.begin() as conn:
            if sqlite:
                self.pgvector_enabled = False
            else:
                try:
                    await conn.execute(sql_text("CREATE EXTENSION IF NOT EXISTS vector"))
                    self.pgvector_enabled = _HAS_PGVECTOR_LIB
                    print("[mind] pgvector extension enabled")
                except Exception as e:
                    self.pgvector_enabled = False
                    print(f"[mind] pgvector not available: {e}. Using JSON embeddings.")

            await conn.run_sync(Base.metadata.create_all)

            if self.pgvector_enabled:
                # Ensure vector column exists for upgrades from JSON-only schema
                try:
                    await conn.execute(
                        sql_text(
                            f"""
                            ALTER TABLE nodes
                            ADD COLUMN IF NOT EXISTS embedding_vec vector({self.embed_dim})
                            """
                        )
                    )
                except Exception as e:
                    print(f"[mind] embedding_vec column ensure: {e}")

                # HNSW index for cosine distance
                try:
                    await conn.execute(
                        sql_text(
                            """
                            CREATE INDEX IF NOT EXISTS nodes_embedding_vec_hnsw
                            ON nodes
                            USING hnsw (embedding_vec vector_cosine_ops)
                            """
                        )
                    )
                    print("[mind] HNSW index ready on embedding_vec")
                except Exception as e:
                    print(f"[mind] HNSW index skipped: {e}")

                # Backfill from JSON embeddings where vector is null
                try:
                    await conn.execute(
                        sql_text(
                            """
                            UPDATE nodes
                            SET embedding_vec = embedding::text::vector
                            WHERE embedding IS NOT NULL
                              AND embedding_vec IS NULL
                              AND jsonb_typeof(to_jsonb(embedding)) = 'array'
                            """
                        )
                    )
                except Exception:
                    # JSON column may not cast cleanly; backfill row-by-row later on read/write
                    pass

        self.session_maker = async_sessionmaker(self.engine, expire_on_commit=False)
        self.is_ready = True
        print(
            f"[mind] Knowledge store initialized (pgvector={self.pgvector_enabled}, dim={self.embed_dim})"
        )

    def _pad_embedding(self, emb: Optional[List[float]]) -> Optional[List[float]]:
        if not emb:
            return None
        if len(emb) == self.embed_dim:
            return [float(x) for x in emb]
        if len(emb) < self.embed_dim:
            return [float(x) for x in emb] + [0.0] * (self.embed_dim - len(emb))
        return [float(x) for x in emb[: self.embed_dim]]

    async def save(self, node: Dict[str, Any]) -> str:
        if not self.session_maker:
            raise RuntimeError("Store not initialized")

        node_id = node.get("id", str(uuid.uuid4()))
        emb = self._pad_embedding(node.get("embedding"))

        async with self.session_maker() as session:
            kwargs = dict(
                id=node_id,
                workspace_id=node["workspace_id"],
                type=node["type"],
                content=node["content"],
                metadata_json=node.get("metadata", {}),
                embedding=emb,
            )
            if self.pgvector_enabled and emb is not None:
                kwargs["embedding_vec"] = emb

            db_node = NodeModel(**kwargs)
            session.add(db_node)
            await session.commit()
            return node_id

    async def get(self, node_id: str, workspace_id: str) -> Optional[Dict]:
        if not self.session_maker:
            return None

        async with self.session_maker() as session:
            result = await session.execute(
                select(NodeModel).where(
                    NodeModel.id == node_id,
                    NodeModel.workspace_id == workspace_id,
                )
            )
            row = result.scalar_one_or_none()
            if not row:
                return None
            return self._row_to_dict(row)

    def _row_to_dict(self, row: NodeModel) -> Dict:
        return {
            "id": row.id,
            "workspace_id": row.workspace_id,
            "type": row.type,
            "content": row.content,
            "metadata": row.metadata_json or {},
            "embedding": row.embedding,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    async def get_links(self, node_id: str, workspace_id: str) -> List[Dict]:
        if not self.session_maker:
            return []

        async with self.session_maker() as session:
            result = await session.execute(
                select(LinkModel).where(
                    ((LinkModel.source_id == node_id) | (LinkModel.target_id == node_id))
                    & (LinkModel.workspace_id == workspace_id)
                )
            )
            return [
                {
                    "id": r.id,
                    "source_id": r.source_id,
                    "target_id": r.target_id,
                    "type": r.link_type,
                    "confidence": r.confidence,
                }
                for r in result.scalars()
            ]

    async def create_link(
        self, source: str, target: str, link_type: str, workspace_id: str
    ) -> Dict:
        if not self.session_maker:
            raise RuntimeError("Store not initialized")

        async with self.session_maker() as session:
            link = LinkModel(
                id=str(uuid.uuid4()),
                workspace_id=workspace_id,
                source_id=source,
                target_id=target,
                link_type=link_type,
                confidence={"method": "explicit", "score": 1.0},
            )
            session.add(link)
            await session.commit()
            return {
                "id": link.id,
                "source_id": source,
                "target_id": target,
                "type": link_type,
                "confidence": link.confidence,
            }

    async def export_subgraph(self, workspace_id: str) -> Dict:
        if not self.session_maker:
            return {"nodes": [], "links": []}

        async with self.session_maker() as session:
            nodes_result = await session.execute(
                select(NodeModel).where(NodeModel.workspace_id == workspace_id)
            )
            links_result = await session.execute(
                select(LinkModel).where(LinkModel.workspace_id == workspace_id)
            )

            nodes = [
                {"id": n.id, "type": n.type, "metadata": n.metadata_json or {}}
                for n in nodes_result.scalars()
            ]
            links = [
                {"source": link.source_id, "target": link.target_id, "type": link.link_type}
                for link in links_result.scalars()
            ]

            return {
                "workspace_id": workspace_id,
                "nodes": nodes,
                "links": links,
                "node_count": len(nodes),
                "link_count": len(links),
            }

    async def search_by_keyword(
        self,
        query: str,
        workspace_id: str,
        filters: Optional[Dict] = None,
        limit: int = 50,
    ) -> List[Dict]:
        if not self.session_maker:
            return []

        async with self.session_maker() as session:
            sql = select(NodeModel).where(NodeModel.workspace_id == workspace_id)

            if filters and "type" in filters:
                sql = sql.where(NodeModel.type == filters["type"])

            result = await session.execute(sql)
            rows = result.scalars().all()

            query_terms = query.lower().split()
            scored = []
            for row in rows:
                content_lower = row.content.lower()
                score = sum(1 for term in query_terms if term in content_lower)
                if score > 0:
                    scored.append((score, row))

            scored.sort(key=lambda x: x[0], reverse=True)

            return [
                {
                    "id": r.id,
                    "type": r.type,
                    "content": r.content[:1000],
                    "metadata": r.metadata_json or {},
                    "score": float(s),
                }
                for s, r in scored[:limit]
            ]

    async def search_by_vector(
        self,
        query_embedding: List[float],
        workspace_id: str,
        filters: Optional[Dict] = None,
        limit: int = 50,
    ) -> List[Dict]:
        if not self.session_maker:
            return []

        query_embedding = self._pad_embedding(query_embedding) or query_embedding

        if self.pgvector_enabled:
            try:
                return await self._search_by_vector_pg(
                    query_embedding, workspace_id, filters, limit
                )
            except Exception as e:
                print(f"[mind] pgvector search failed, falling back to JSON: {e}")

        return await self._search_by_vector_json(
            query_embedding, workspace_id, filters, limit
        )

    async def _search_by_vector_pg(
        self,
        query_embedding: List[float],
        workspace_id: str,
        filters: Optional[Dict],
        limit: int,
    ) -> List[Dict]:
        """Cosine distance via pgvector <=> operator, scoped by workspace_id."""
        type_filter = ""
        params: Dict[str, Any] = {
            "ws": workspace_id,
            "q": str(query_embedding),
            "lim": limit,
        }
        if filters and filters.get("type"):
            type_filter = "AND type = :ntype"
            params["ntype"] = filters["type"]

        sql = f"""
            SELECT id, type, left(content, 1000) AS content, metadata_json,
                   1 - (embedding_vec <=> CAST(:q AS vector)) AS score
            FROM nodes
            WHERE workspace_id = :ws
              AND embedding_vec IS NOT NULL
              {type_filter}
            ORDER BY embedding_vec <=> CAST(:q AS vector)
            LIMIT :lim
        """
        async with self.session_maker() as session:
            result = await session.execute(sql_text(sql), params)
            rows = result.mappings().all()
            return [
                {
                    "id": r["id"],
                    "type": r["type"],
                    "content": r["content"],
                    "metadata": r["metadata_json"] or {},
                    "score": float(r["score"] or 0.0),
                }
                for r in rows
            ]

    async def _search_by_vector_json(
        self,
        query_embedding: List[float],
        workspace_id: str,
        filters: Optional[Dict],
        limit: int,
    ) -> List[Dict]:
        async with self.session_maker() as session:
            sql = select(NodeModel).where(
                NodeModel.workspace_id == workspace_id,
                NodeModel.embedding.isnot(None),
            )
            if filters and "type" in filters:
                sql = sql.where(NodeModel.type == filters["type"])

            result = await session.execute(sql)
            rows = result.scalars().all()

            scored = []
            for row in rows:
                emb = row.embedding
                if not emb:
                    continue
                emb = self._pad_embedding(emb) or emb
                similarity = _cosine(query_embedding, emb)
                scored.append((similarity, row))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [
                {
                    "id": r.id,
                    "type": r.type,
                    "content": r.content[:1000],
                    "metadata": r.metadata_json or {},
                    "score": float(s),
                }
                for s, r in scored[:limit]
            ]

    async def get_all_nodes(self, workspace_id: str, limit: int = 1000) -> List[Dict]:
        if not self.session_maker:
            return []

        async with self.session_maker() as session:
            result = await session.execute(
                select(NodeModel)
                .where(NodeModel.workspace_id == workspace_id)
                .limit(limit)
            )
            return [
                {
                    "id": r.id,
                    "type": r.type,
                    "content": r.content,
                    "metadata": r.metadata_json or {},
                    "embedding": r.embedding,
                }
                for r in result.scalars()
            ]

    async def close(self):
        if self.engine:
            await self.engine.dispose()
