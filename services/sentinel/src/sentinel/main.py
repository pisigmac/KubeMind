import os
import json
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from sentinel.models import SpanIngest, SpanQuery, SpanResponse, MetricsResponse, ExportResponse
from sentinel.storage import TraceStore
from sentinel.streaming import ConnectionManager
from sentinel.redaction import redact_attributes
from sentinel.guardrails import annotate_attributes
from sentinel import metrics as prom_metrics
from sentinel import otel as otel_export
import hashlib

# ── Global state ─────────────────────────────────────────────────
store: TraceStore | None = None
manager: ConnectionManager | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global store, manager

    store = TraceStore()
    manager = ConnectionManager()

    # Start background tasks
    prune_task = asyncio.create_task(_prune_loop())
    heartbeat_task = asyncio.create_task(_heartbeat_loop())

    print(
        f"[sentinel] Initialized "
        f"(redaction=on, otlp={'on' if otel_export.enabled() else 'off'})"
    )
    yield

    prune_task.cancel()
    heartbeat_task.cancel()
    await otel_export.close()

async def _prune_loop():
    while True:
        try:
            await asyncio.sleep(86400)  # Daily
            if store:
                deleted = store.prune_old(days=90)
                print(f"[sentinel] Pruned {deleted} old spans")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[sentinel] Prune error: {e}")

async def _heartbeat_loop():
    while True:
        try:
            await asyncio.sleep(30)
            if manager:
                count = manager.get_connection_count()
                if count > 0:
                    await manager.broadcast(json.dumps({
                        "type": "heartbeat",
                        "timestamp": datetime.utcnow().isoformat(),
                        "connections": count,
                    }))
        except asyncio.CancelledError:
            break
        except Exception:
            pass

app = FastAPI(
    title="KubeMind Sentinel",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health ──────────────────────────────────────────────────────
@app.get("/health")
async def health():
    stats = store.get_stats() if store else {}
    return {
        "status": "healthy",
        "service": "sentinel",
        "version": "0.2.0",
        "spans_stored": stats.get("total_spans", 0),
        "workspaces": stats.get("workspaces", 0),
        "websocket_connections": manager.get_connection_count() if manager else 0,
        "redaction": True,
        "otlp": otel_export.enabled(),
    }

# ── Span Ingestion ─────────────────────────────────────────────
@app.post("/v1/spans")
async def ingest_span(req: SpanIngest, request: Request):
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")

    payload = req.model_dump()
    # Injection scoring first (on original text), then PII redaction for storage
    attrs = annotate_attributes(payload.get("attributes") or {})
    attrs, redacted_modes = redact_attributes(attrs)
    payload["attributes"] = attrs

    span_id = store.save_span(payload)

    prom_metrics.record_span(payload.get("service", "unknown"), payload.get("status", "ok"))
    if redacted_modes:
        prom_metrics.record_redaction(len(redacted_modes))
    if attrs.get("injection_flags"):
        prom_metrics.record_injection_flagged()

    await otel_export.export_span(payload)

    # Broadcast to WebSocket subscribers (already redacted)
    if manager:
        await manager.send_to_workspace(
            req.workspace_id,
            json.dumps({"type": "span", "data": payload})
        )

    return {
        "status": "ok",
        "span_id": span_id,
        "redacted_fields": redacted_modes,
        "injection_score": attrs.get("injection_score", 0.0),
    }

# ── Span Query ──────────────────────────────────────────────────
@app.post("/v1/spans/query")
async def query_spans(req: SpanQuery, request: Request):
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")

    results = store.query(
        workspace_id=req.workspace_id,
        service=req.service,
        operation=req.operation,
        status=req.status,
        start_time=req.start_time,
        end_time=req.end_time,
        limit=req.limit,
        offset=req.offset,
    )

    return {
        "spans": results,
        "count": len(results),
        "limit": req.limit,
        "offset": req.offset,
    }

@app.get("/v1/spans")
async def get_spans(
    workspace_id: str = "default",
    service: str = None,
    operation: str = None,
    status: str = None,
    limit: int = 100,
    offset: int = 0,
):
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")

    results = store.query(
        workspace_id=workspace_id,
        service=service,
        operation=operation,
        status=status,
        limit=limit,
        offset=offset,
    )

    return {
        "spans": results,
        "count": len(results),
        "limit": limit,
        "offset": offset,
    }

# ── Metrics ────────────────────────────────────────────────────
@app.get("/v1/metrics")
async def get_metrics(
    workspace_id: str = "default",
    hours: int = 24,
):
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")

    return store.aggregate(workspace_id, hours=hours)

# ── Export ─────────────────────────────────────────────────────
@app.get("/v1/export")
async def export_traces(
    workspace_id: str = "default",
    hours: int = None,
):
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")

    data = store.export(workspace_id, hours=hours)
    # Enrich with redaction summary + checksum for batch integrity
    redacted = 0
    for s in data.get("spans") or []:
        attrs = s.get("attributes")
        if isinstance(attrs, str):
            try:
                attrs = json.loads(attrs)
            except Exception:
                attrs = {}
        if isinstance(attrs, dict) and attrs.get("attributes_redacted_fields"):
            redacted += 1
    raw = json.dumps(data.get("spans") or [], sort_keys=True, default=str)
    data["redaction"] = {
        "spans_with_redaction": redacted,
        "checksum_sha256": hashlib.sha256(raw.encode()).hexdigest(),
    }
    return data

# ── Telemetry alias (landing / Phase 3) ────────────────────────
@app.get("/v1/telemetry/traces")
async def telemetry_traces(
    workspace_id: str = "default",
    service: str = None,
    operation: str = None,
    status: str = None,
    limit: int = 100,
    offset: int = 0,
):
    """Alias of GET /v1/spans for landing/SDK compatibility."""
    return await get_spans(
        workspace_id=workspace_id,
        service=service,
        operation=operation,
        status=status,
        limit=limit,
        offset=offset,
    )


# ── Prometheus scrape endpoint ─────────────────────────────────
@app.get("/metrics")
async def prometheus_metrics():
    ws = manager.get_connection_count() if manager else 0
    body = prom_metrics.render_prometheus(websocket_connections=ws)
    return PlainTextResponse(content=body, media_type="text/plain; version=0.0.4")


# ── Stats ──────────────────────────────────────────────────────
@app.get("/v1/stats")
async def get_stats():
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")

    return store.get_stats()

# ── WebSocket Streaming ─────────────────────────────────────────
@app.websocket("/v1/stream")
async def websocket_stream(websocket: WebSocket):
    if not manager:
        await websocket.close(code=1011)
        return

    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "")

                if msg_type == "subscribe":
                    workspace_id = msg.get("workspace_id", "default")
                    await manager.subscribe(websocket, workspace_id)

                elif msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong", "timestamp": datetime.utcnow().isoformat()}))

                else:
                    await websocket.send_text(json.dumps({"type": "ack", "received": data}))

            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON"}))

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
