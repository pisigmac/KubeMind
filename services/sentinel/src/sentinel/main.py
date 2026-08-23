import json
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from kubemind_auth import (
    API_KEY_HEADER,
    WORKSPACE_HEADER,
    AuthError,
    Authenticator,
    AuthResult,
    cors_origins,
)

from sentinel.models import (
    SpanIngest,
    SpanQuery,
    RetentionRequest,
)
from sentinel.storage import TraceStore
from sentinel.ledger import AuditLedger
from sentinel.streaming import ConnectionManager
from sentinel.redaction import redact_attributes
from sentinel.guardrails import annotate_attributes
from sentinel import metrics as prom_metrics
from sentinel import otel as otel_export
import hashlib

# ── Global state ─────────────────────────────────────────────────
store: TraceStore | None = None
manager: ConnectionManager | None = None
ledger: AuditLedger | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global store, manager, ledger

    store = TraceStore()
    manager = ConnectionManager()
    try:
        ledger = AuditLedger()
    except Exception as e:
        # The span store still works without it, but the compliance claim does
        # not, so this is loud rather than silent.
        ledger = None
        print(f"[sentinel] AUDIT LEDGER UNAVAILABLE: {e}")

    # Start background tasks
    prune_task = asyncio.create_task(_prune_loop())
    heartbeat_task = asyncio.create_task(_heartbeat_loop())

    print(
        f"[sentinel] Initialized "
        f"(redaction=on, otlp={'on' if otel_export.enabled() else 'off'}, "
        f"ledger={'on' if ledger else 'off'})"
    )
    yield

    prune_task.cancel()
    heartbeat_task.cancel()
    await otel_export.close()
    if ledger:
        ledger.close()

async def _prune_loop():
    while True:
        try:
            await asyncio.sleep(86400)  # Daily
            if store:
                deleted = store.prune_old(days=90)
                print(f"[sentinel] Pruned {deleted} old spans")
            if ledger:
                # Per-workspace retention, and a legal hold suspends deletion
                # rather than being a note in a runbook.
                result = ledger.prune()
                total = sum(v.get("deleted", 0) for v in result["pruned"].values())
                held = [w for w, v in result["pruned"].items() if v.get("skipped")]
                print(
                    f"[sentinel] Ledger pruned {total} entries"
                    + (f", {len(held)} workspace(s) under legal hold" if held else "")
                )
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
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", API_KEY_HEADER, WORKSPACE_HEADER],
)

authenticator = Authenticator.from_config()
print(authenticator.startup_banner("sentinel"))


async def get_auth(request: Request) -> AuthResult:
    try:
        return authenticator.authenticate(
            request.headers.get(API_KEY_HEADER),
            request.headers.get(WORKSPACE_HEADER),
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


def _scope(auth: AuthResult, requested: Optional[str]) -> str:
    """Resolve a workspace named in a query string or body against the key.

    Several read endpoints took `workspace_id` as a plain query parameter, so
    anyone who guessed a tenant name could read its traces. An authenticated
    caller may only ever name its own workspace.
    """
    try:
        return authenticator.resolve_requested_workspace(auth, requested)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


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
async def ingest_span(req: SpanIngest, request: Request, auth=Depends(get_auth)):
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")

    payload = req.model_dump()
    # Bind the record to the caller's workspace. Accepting the body's value
    # would let anyone write audit entries attributed to another tenant, which
    # is the difference between a trace log and evidence.
    payload["workspace_id"] = _scope(auth, payload.get("workspace_id"))
    # Injection scoring first (on original text), then PII redaction for storage
    attrs = annotate_attributes(payload.get("attributes") or {})
    attrs, redacted_modes = redact_attributes(attrs)
    payload["attributes"] = attrs

    span_id = store.save_span(payload)

    # The queryable table stays as it is; the ledger is the copy you can prove
    # was not edited afterwards. Written post-redaction so the chain commits to
    # exactly the bytes retained.
    ledger_entry = None
    if ledger:
        try:
            ledger_entry = ledger.append(
                payload["workspace_id"],
                payload,
                entry_type="decision" if attrs.get("intent") else "span",
            )
        except Exception as e:
            print(f"[sentinel] ledger append failed: {e}")

    prom_metrics.record_span(payload.get("service", "unknown"), payload.get("status", "ok"))
    if redacted_modes:
        prom_metrics.record_redaction(len(redacted_modes))
    if attrs.get("injection_flags"):
        prom_metrics.record_injection_flagged()

    await otel_export.export_span(payload)

    # Broadcast to WebSocket subscribers (already redacted)
    if manager:
        await manager.send_to_workspace(
            payload["workspace_id"],
            json.dumps({"type": "span", "data": payload})
        )

    return {
        "status": "ok",
        "span_id": span_id,
        "redacted_fields": redacted_modes,
        "injection_score": attrs.get("injection_score", 0.0),
        # Returned so a caller can record its own receipt and later prove the
        # entry was accepted unchanged.
        "ledger": ledger_entry,
    }


# ── Audit ledger ───────────────────────────────────────────────
@app.get("/v1/audit/verify")
async def verify_audit_chain(
    workspace_id: str = None,
    limit: int = None,
    auth=Depends(get_auth),
):
    """Walk the hash chain and report the first entry that disagrees.

    A 200 with `valid: false` is the interesting answer: the chain is intact
    enough to read, and something in it has been changed.
    """
    if not ledger:
        raise HTTPException(status_code=503, detail="Audit ledger not initialized")
    return ledger.verify(_scope(auth, workspace_id), limit=limit)


@app.get("/v1/audit/head")
async def audit_head(workspace_id: str = None, auth=Depends(get_auth)):
    """Current head hash, for anchoring outside this database.

    A tamper that rewrites the whole chain is undetectable from the inside.
    Recording this value somewhere the database cannot reach is what closes
    that gap.
    """
    if not ledger:
        raise HTTPException(status_code=503, detail="Audit ledger not initialized")
    return ledger.head(_scope(auth, workspace_id))


@app.get("/v1/audit/entries")
async def audit_entries_list(
    workspace_id: str = None,
    limit: int = 100,
    offset: int = 0,
    entry_type: str = None,
    auth=Depends(get_auth),
):
    if not ledger:
        raise HTTPException(status_code=503, detail="Audit ledger not initialized")
    ws = _scope(auth, workspace_id)
    return {
        "workspace_id": ws,
        "entries": ledger.entries(ws, limit=limit, offset=offset, entry_type=entry_type),
    }


@app.get("/v1/audit/retention")
async def get_retention(workspace_id: str = None, auth=Depends(get_auth)):
    if not ledger:
        raise HTTPException(status_code=503, detail="Audit ledger not initialized")
    return ledger.get_retention(_scope(auth, workspace_id))


@app.post("/v1/audit/retention")
async def set_retention(req: RetentionRequest, auth=Depends(get_auth)):
    """Set a workspace's retention window, or place it under legal hold."""
    if not ledger:
        raise HTTPException(status_code=503, detail="Audit ledger not initialized")
    return ledger.set_retention(
        _scope(auth, req.workspace_id),
        retention_days=req.retention_days,
        legal_hold=req.legal_hold,
    )


@app.get("/v1/audit/stats")
async def audit_stats(auth=Depends(get_auth)):
    if not ledger:
        raise HTTPException(status_code=503, detail="Audit ledger not initialized")
    return ledger.stats()

# ── Span Query ──────────────────────────────────────────────────
@app.post("/v1/spans/query")
async def query_spans(req: SpanQuery, request: Request, auth=Depends(get_auth)):
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")

    results = store.query(
        workspace_id=_scope(auth, req.workspace_id),
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
    workspace_id: str = None,
    service: str = None,
    operation: str = None,
    status: str = None,
    limit: int = 100,
    offset: int = 0,
    auth=Depends(get_auth),
):
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")

    results = store.query(
        workspace_id=_scope(auth, workspace_id),
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
    workspace_id: str = None,
    hours: int = 24,
    auth=Depends(get_auth),
):
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")

    return store.aggregate(_scope(auth, workspace_id), hours=hours)

# ── Export ─────────────────────────────────────────────────────
@app.get("/v1/export")
async def export_traces(
    workspace_id: str = None,
    hours: int = None,
    auth=Depends(get_auth),
):
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")

    data = store.export(_scope(auth, workspace_id), hours=hours)
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
    workspace_id: str = None,
    service: str = None,
    operation: str = None,
    status: str = None,
    limit: int = 100,
    offset: int = 0,
    auth=Depends(get_auth),
):
    """Alias of GET /v1/spans for landing/SDK compatibility."""
    return await get_spans(
        workspace_id=workspace_id,
        service=service,
        operation=operation,
        status=status,
        limit=limit,
        offset=offset,
        auth=auth,
    )


# ── Prometheus scrape endpoint ─────────────────────────────────
@app.get("/metrics")
async def prometheus_metrics():
    ws = manager.get_connection_count() if manager else 0
    body = prom_metrics.render_prometheus(websocket_connections=ws)
    return PlainTextResponse(content=body, media_type="text/plain; version=0.0.4")


# ── Stats ──────────────────────────────────────────────────────
@app.get("/v1/stats")
async def get_stats(auth=Depends(get_auth)):
    if not store:
        raise HTTPException(status_code=503, detail="Store not initialized")

    stats = store.get_stats()
    if auth.authenticated:
        # Global counts reveal how many other tenants exist and how busy they
        # are. Scope them once we know who is asking.
        stats = dict(stats)
        stats.pop("workspaces", None)
        stats["workspace_id"] = auth.workspace_id
    return stats

# ── WebSocket Streaming ─────────────────────────────────────────
@app.websocket("/v1/stream")
async def websocket_stream(websocket: WebSocket):
    if not manager:
        await websocket.close(code=1011)
        return

    # Browsers cannot set headers on a WebSocket handshake, so the key may
    # also arrive as a query parameter.
    try:
        ws_auth = authenticator.authenticate(
            websocket.headers.get(API_KEY_HEADER)
            or websocket.query_params.get("api_key"),
            websocket.headers.get(WORKSPACE_HEADER),
        )
    except AuthError:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "")

                if msg_type == "subscribe":
                    # A live span feed is the same data as /v1/spans, so it
                    # gets the same scoping.
                    try:
                        workspace_id = authenticator.resolve_requested_workspace(
                            ws_auth, msg.get("workspace_id")
                        )
                    except AuthError as e:
                        await websocket.send_text(
                            json.dumps({"type": "error", "message": str(e)})
                        )
                        continue
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
