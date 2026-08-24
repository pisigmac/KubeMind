from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from beacon_trace.models import SpanIngest
from beacon_trace.storage import TraceStore
from beacon_trace.streaming import ConnectionManager
import time
import json

app = FastAPI(title="beacon-trace", version="0.1.0")

store: TraceStore = None
manager: ConnectionManager = None

@app.on_event("startup")
async def startup():
    global store, manager
    store = TraceStore()
    await store.init()
    manager = ConnectionManager()

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "beacon-trace",
        "version": "0.1.0",
        "timestamp": time.isoformat(),
    }

@app.post("/v1/spans")
async def ingest_span(req: SpanIngest, request: Request):
    await store.save_span(req.model_dump())
    await manager.broadcast(json.dumps({"type": "span", "data": req.model_dump()}))
    return {"status": "ok"}

@app.get("/v1/spans")
async def query_spans(request: Request):
    workspace_id = request.headers.get("X-Workspace-ID", "default")
    service = request.query_params.get("service")
    limit = int(request.query_params.get("limit", 100))
    return await store.query(workspace_id, service, limit)

@app.get("/v1/metrics")
async def get_metrics(request: Request):
    workspace_id = request.headers.get("X-Workspace-ID", "default")
    return await store.aggregate(workspace_id)

@app.get("/v1/export")
async def export_traces(request: Request):
    workspace_id = request.headers.get("X-Workspace-ID", "default")
    return await store.export(workspace_id)

@app.websocket("/v1/stream")
async def websocket_stream(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back or handle subscription filters
            await websocket.send_text(json.dumps({"type": "ack", "received": data}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
