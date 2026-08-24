# Mind vector backends

| Backend | Module | Status |
|---------|--------|--------|
| **pgvector** (default) | `pgvector.py` | Implemented via `KnowledgeStore` |
| Milvus | `milvus.py` | Stub — `NotImplementedError` |
| Neo4j | `neo4j.py` | Stub — `NotImplementedError` |

Interface: `VectorBackend` in `base.py` (`upsert`, `search`, `delete`, `get`).

Default path remains hybrid search in `HybridSearcher` + `KnowledgeStore`.  
Swap backends later via env `MIND_VECTOR_BACKEND=pgvector|milvus|neo4j`.
