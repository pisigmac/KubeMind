from contextlib import asynccontextmanager

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

from agents.models import (
    MissionRequest, MissionResponse, MissionStatus, ToolInvokeRequest
)
from agents.engine import AgentEngine
from agents.tools import ToolRegistry
from agents.planner import Planner
from agents.memory import MemoryManager
from agents.tracer import TracerClient

# ── Global state ─────────────────────────────────────────────────
engine: AgentEngine | None = None
tools: ToolRegistry | None = None
planner: Planner | None = None
memory: MemoryManager | None = None
sentinel: TracerClient | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine, tools, planner, memory, sentinel

    tools = ToolRegistry()
    await tools.load()

    planner = Planner()
    await planner.init()

    memory = MemoryManager()
    await memory.init()

    sentinel = TracerClient(service_name="agents")
    await sentinel.init()

    engine = AgentEngine(tools=tools, planner=planner, memory=memory, tracer=sentinel)
    await engine.init()

    print("[agents] All services initialized")
    yield

    await engine.close()
    await memory.close()

app = FastAPI(
    title="agents",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", API_KEY_HEADER, WORKSPACE_HEADER],
)

authenticator = Authenticator.from_config()
print(authenticator.startup_banner("agents"))


# ── Dependencies ─────────────────────────────────────────────────
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

    Missions execute tools and spend tokens, so a forged header here is a way
    to run work against someone else's budget.
    """
    return (await get_auth(request)).workspace_id

# ── Health ──────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "agents",
        "version": "0.1.0",
        "tools_loaded": len(tools.tools) if tools else 0,
        "engine_ready": engine.is_ready if engine else False,
    }

# ── Missions ─────────────────────────────────────────────────────
@app.post("/v1/missions", response_model=MissionResponse)
async def create_mission(req: MissionRequest, request: Request, workspace_id: str = Depends(get_workspace)):
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    if req.mode == "sync":
        result = await engine.run_sync(req.prompt, workspace_id, model=req.model)
        return MissionResponse(
            id=result["id"],
            status=result["status"],
            result=result.get("output"),
            error=result.get("error"),
            tool_calls=result.get("tool_calls", 0),
            tokens_used=result.get("tokens_used", 0),
            duration_ms=result.get("duration_ms", 0),
        )

    elif req.mode == "async":
        mission_id = await engine.run_async(req.prompt, workspace_id, model=req.model)
        return MissionResponse(id=mission_id, status="queued")

    else:
        raise HTTPException(status_code=400, detail=f"Unknown mode: {req.mode}")

@app.get("/v1/missions/{mission_id}", response_model=MissionStatus)
async def get_mission(mission_id: str, request: Request, workspace_id: str = Depends(get_workspace)):
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return await engine.get_status(mission_id, workspace_id)

@app.post("/v1/missions/{mission_id}/cancel")
async def cancel_mission(mission_id: str, request: Request, workspace_id: str = Depends(get_workspace)):
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    await engine.cancel(mission_id, workspace_id)
    return {"status": "cancelled", "id": mission_id}

@app.get("/v1/missions")
async def list_missions(request: Request, workspace_id: str = Depends(get_workspace), limit: int = 50):
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return await engine.list_missions(workspace_id, limit)

# ── Tools ───────────────────────────────────────────────────────
@app.post("/v1/tools/invoke")
async def invoke_tool(req: ToolInvokeRequest, request: Request, workspace_id: str = Depends(get_workspace)):
    if not tools:
        raise HTTPException(status_code=503, detail="Tools not initialized")
    result = await tools.invoke(req.tool, req.arguments, workspace_id)
    return result

@app.get("/v1/tools")
async def list_tools():
    if not tools:
        raise HTTPException(status_code=503, detail="Tools not initialized")
    return tools.list_schema()
