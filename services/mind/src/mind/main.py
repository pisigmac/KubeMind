import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import yaml
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from kubemind_auth import (
    API_KEY_HEADER,
    WORKSPACE_HEADER,
    AuthError,
    Authenticator,
    AuthResult,
    cors_origins,
)

from mind.models import (
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    NodeResponse,
    LinkRequest,
    NodeType,
)
from mind.storage import KnowledgeStore
from mind.embeddings import EmbeddingGenerator
from mind.search import HybridSearcher
from mind.connectors import ConnectorRegistry
from mind.links import LinkDetector
from mind.tracer import TracerClient
from mind.chunking import expand_nodes_with_chunks

# ── Global state ─────────────────────────────────────────────────
store: Optional[KnowledgeStore] = None
embedder: Optional[EmbeddingGenerator] = None
searcher: Optional[HybridSearcher] = None
connectors: Optional[ConnectorRegistry] = None
link_detector: Optional[LinkDetector] = None
sentinel: Optional[TracerClient] = None
chunk_cfg: dict = {
    "max_tokens": 512,
    "overlap_tokens": 64,
    "strategy": "recursive_character",
}


def _load_knowledge_config() -> dict:
    path = os.environ.get("KUBEMIND_MIND_CONFIG", "config/knowledge.yaml")
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global store, embedder, searcher, connectors, link_detector, sentinel, chunk_cfg

    cfg = _load_knowledge_config()
    chunk_cfg = {
        **chunk_cfg,
        **(cfg.get("chunking") or {}),
    }

    store = KnowledgeStore()
    await store.init()

    embedder = EmbeddingGenerator()
    await embedder.init()

    searcher = HybridSearcher(store, embedder)

    connectors = ConnectorRegistry()
    await connectors.load()

    link_detector = LinkDetector(store)

    sentinel = TracerClient(service_name="mind")
    await sentinel.init()

    print(
        f"[mind] Initialized (pgvector={store.pgvector_enabled}, "
        f"chunk max_tokens={chunk_cfg.get('max_tokens')})"
    )
    yield

    await store.close()
    await embedder.close()


app = FastAPI(
    title="KubeMind Mind",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", API_KEY_HEADER, WORKSPACE_HEADER],
)

authenticator = Authenticator.from_config()
authenticator.assert_production_safe("mind")
print(authenticator.startup_banner("mind"))


async def get_auth(request: Request) -> AuthResult:
    try:
        return authenticator.authenticate(
            request.headers.get(API_KEY_HEADER),
            request.headers.get(WORKSPACE_HEADER),
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


async def get_workspace(request: Request) -> str:
    """Workspace comes from the key when one is configured, never the header.

    Retrieved knowledge is the most sensitive thing this service holds, so a
    forged header here reads another tenant's documents.
    """
    return (await get_auth(request)).workspace_id


async def _run_query(req: QueryRequest, workspace_id: str) -> QueryResponse:
    if not searcher:
        raise HTTPException(status_code=503, detail="Search not initialized")

    start = time.time()
    results = await searcher.search(
        query=req.query,
        filters=req.filters,
        workspace_id=workspace_id,
        top_k=req.top_k or 10,
    )
    if sentinel:
        await sentinel.log_request(
            workspace_id,
            "query",
            (time.time() - start) * 1000,
            attributes={"result_count": len(results), "query": req.query[:100]},
        )

    return QueryResponse(
        query=req.query,
        results=results,
        count=len(results),
        workspace_id=workspace_id,
    )


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "mind",
        "version": "0.2.0",
        "embedder_ready": embedder.is_ready if embedder else False,
        "store_ready": store.is_ready if store else False,
        "pgvector": store.pgvector_enabled if store else False,
        "chunking": chunk_cfg,
    }


@app.post("/v1/ingest", response_model=IngestResponse)
async def ingest(
    req: IngestRequest, request: Request, workspace_id: str = Depends(get_workspace)
):
    if not connectors or not store or not embedder:
        raise HTTPException(status_code=503, detail="Knowledge services not initialized")

    if req.content is not None:
        raw_nodes = [
            {
                "id": str(uuid.uuid4()),
                "workspace_id": workspace_id,
                "type": req.type.value if hasattr(req.type, "value") else str(req.type),
                "content": req.content[:200000],
                "metadata": {
                    "filename": req.source,
                    "path": req.source,
                    "uploaded": True,
                },
            }
        ]
    else:
        connector = connectors.get_for_source(req.source)
        if not connector:
            raise HTTPException(status_code=400, detail=f"No connector for source: {req.source}")
        raw_nodes = await connector.ingest(req.source, req.type, workspace_id)

    # Chunk long documents
    raw_nodes = expand_nodes_with_chunks(
        raw_nodes,
        max_tokens=int(chunk_cfg.get("max_tokens", 512)),
        overlap_tokens=int(chunk_cfg.get("overlap_tokens", 64)),
        strategy=str(chunk_cfg.get("strategy", "recursive_character")),
    )

    saved_nodes = []
    for node in raw_nodes:
        node["workspace_id"] = workspace_id  # enforce tenant
        start = time.time()
        embedding = await embedder.embed(node["content"])
        node["embedding"] = embedding
        node_id = await store.save(node)
        saved_nodes.append(node_id)

        if sentinel:
            await sentinel.log_request(
                workspace_id,
                "ingest",
                (time.time() - start) * 1000,
                attributes={
                    "node_type": node["type"],
                    "source": req.source,
                    "chunk_index": (node.get("metadata") or {}).get("chunk_index"),
                },
            )

    if saved_nodes and link_detector:
        await link_detector.detect_links(saved_nodes, workspace_id)

    return IngestResponse(
        ingested=len(saved_nodes),
        node_ids=saved_nodes,
        workspace_id=workspace_id,
    )


@app.get("/v1/nodes/{node_id}", response_model=NodeResponse)
async def get_node(
    node_id: str, request: Request, workspace_id: str = Depends(get_workspace)
):
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")

    node = await store.get(node_id, workspace_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    links = await store.get_links(node_id, workspace_id)
    return NodeResponse(
        id=node["id"],
        type=node["type"],
        workspace_id=node["workspace_id"],
        content=node["content"],
        metadata=node["metadata"],
        created_at=node["created_at"],
        updated_at=node["updated_at"],
        links=links,
    )


@app.post("/v1/query", response_model=QueryResponse)
async def query(
    req: QueryRequest, request: Request, workspace_id: str = Depends(get_workspace)
):
    return await _run_query(req, workspace_id)


@app.post("/v1/memory/query", response_model=QueryResponse)
async def memory_query(
    req: QueryRequest, request: Request, workspace_id: str = Depends(get_workspace)
):
    """Landing/SDK alias for hybrid knowledge query."""
    return await _run_query(req, workspace_id)


@app.post("/v1/link")
async def create_link(
    req: LinkRequest, request: Request, workspace_id: str = Depends(get_workspace)
):
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")

    link = await store.create_link(
        req.source_id, req.target_id, req.link_type, workspace_id
    )
    return link


@app.get("/v1/graph")
async def export_graph(request: Request, workspace_id: str = Depends(get_workspace)):
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")

    return await store.export_subgraph(workspace_id)


@app.get("/v1/types")
async def list_types():
    return {
        "types": [t.value for t in NodeType],
        "schemas": {
            NodeType.DOCUMENT.value: ["title", "source_url", "content", "checksum"],
            NodeType.CODE.value: ["repo", "path", "language", "content", "commit_sha"],
            NodeType.CONVERSATION.value: [
                "agent_id",
                "mission_id",
                "turn_index",
                "content",
            ],
            NodeType.AGENT_MEMORY.value: ["agent_id", "key", "value", "timestamp"],
            NodeType.PLAN.value: ["mission_id", "todos", "status"],
        },
    }
