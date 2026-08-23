import os
import uuid
import json
import httpx
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text, JSON, Integer, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class MissionModel(Base):
    __tablename__ = "missions"
    id = Column(String, primary_key=True)
    workspace_id = Column(String, index=True, nullable=False)
    prompt = Column(Text, nullable=False)
    status = Column(String, default="queued")  # queued | running | completed | failed | cancelled
    output = Column(Text)
    error = Column(Text)
    plan = Column(JSON)
    tool_calls = Column(JSON, default=list)
    tokens_used = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

class AgentEngine:
    def __init__(self, tools, planner, memory, sentinel=None, tracer=None):
        self.tools = tools
        self.planner = planner
        self.memory = memory
        self.sentinel = sentinel or tracer
        self.router_url = os.environ.get("ROUTER_URL", "http://localhost:9080")
        self.mind_url = os.environ.get("MIND_URL", "http://localhost:9081")
        self.sentinel_url = os.environ.get("SENTINEL_URL", "http://localhost:9083")
        self.default_model = os.environ.get("AGENT_MODEL", "llama3.1")
        self.max_steps = int(os.environ.get("MAX_STEPS", "20"))
        self.engine = None
        self.session_maker = None
        self.is_ready = False
        self.client = None

    async def init(self):
        db_url = os.environ.get("DATABASE_URL", "postgresql://tricore:tricore@localhost:5432/tricore")
        async_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        self.engine = create_async_engine(async_url, echo=False)

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self.session_maker = async_sessionmaker(self.engine, expire_on_commit=False)
        self.client = httpx.AsyncClient(timeout=120)
        self.is_ready = True
        print("[agents] Engine initialized")

    async def run_sync(self, prompt: str, workspace_id: str, model: Optional[str] = None) -> Dict[str, Any]:
        mission_id = str(uuid.uuid4())
        start_time = time.time()

        # Save mission
        async with self.session_maker() as session:
            mission = MissionModel(
                id=mission_id,
                workspace_id=workspace_id,
                prompt=prompt,
                status="running",
            )
            session.add(mission)
            await session.commit()

        try:
            # 1. Plan
            available_tools = list(self.tools.tools.keys())
            plan_start = time.time()
            plan = await self.planner.plan(prompt, available_tools, model=model)
            if self.sentinel:
                await self.sentinel.log_request(workspace_id, "plan", (time.time() - plan_start) * 1000)

            # Update mission with plan
            async with self.session_maker() as session:
                mission = await session.get(MissionModel, mission_id)
                mission.plan = plan
                await session.commit()

            # 2. Execute todos
            output_parts = []
            tool_calls = []
            total_tokens = 0

            todos = plan.get("todos", [{"step": 1, "task": prompt, "tool": None}])

            for i, todo in enumerate(todos[:self.max_steps]):
                if await self._is_cancelled(mission_id, workspace_id):
                    raise Exception("Mission cancelled by user")

                step_start = time.time()
                step_result = await self._execute_step(
                    todo, workspace_id, mission_id, model, i
                )
                if self.sentinel:
                    await self.sentinel.log_tool_call(workspace_id, todo.get("tool") or "llm",
                        (time.time() - step_start) * 1000,
                        status="ok" if not step_result.get("error") else "error",
                        attributes={"step": i, "task": todo.get("task", "")[:100]})

                output_parts.append(f"## Step {i+1}: {todo.get('task', 'Execute')}")
                output_parts.append(step_result.get("output", ""))
                output_parts.append("")

                tool_calls.extend(step_result.get("tool_calls", []))
                total_tokens += step_result.get("tokens_used", 0)

            output = "\n\n".join(output_parts)
            duration_ms = int((time.time() - start_time) * 1000)

            # Update mission as completed
            async with self.session_maker() as session:
                mission = await session.get(MissionModel, mission_id)
                mission.status = "completed"
                mission.output = output
                mission.tool_calls = tool_calls
                mission.tokens_used = total_tokens
                mission.duration_ms = duration_ms
                mission.completed_at = datetime.utcnow()
                await session.commit()

            return {
                "id": mission_id,
                "status": "completed",
                "output": output,
                "tool_calls": len(tool_calls),
                "tokens_used": total_tokens,
                "duration_ms": duration_ms,
            }

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            async with self.session_maker() as session:
                mission = await session.get(MissionModel, mission_id)
                mission.status = "failed"
                mission.error = str(e)
                mission.duration_ms = duration_ms
                await session.commit()

            return {
                "id": mission_id,
                "status": "failed",
                "error": str(e),
                "duration_ms": duration_ms,
            }

    async def run_async(self, prompt: str, workspace_id: str, model: Optional[str] = None) -> str:
        mission_id = str(uuid.uuid4())
        async with self.session_maker() as session:
            mission = MissionModel(
                id=mission_id,
                workspace_id=workspace_id,
                prompt=prompt,
                status="queued",
            )
            session.add(mission)
            await session.commit()

        # TODO: Background task queue (Celery, RQ, or asyncio.create_task)
        # For now, just mark as queued
        return mission_id

    async def get_status(self, mission_id: str, workspace_id: str) -> Dict:
        async with self.session_maker() as session:
            mission = await session.get(MissionModel, mission_id)
            if not mission or mission.workspace_id != workspace_id:
                raise Exception("Mission not found")

            return {
                "id": mission.id,
                "status": mission.status,
                "prompt": mission.prompt,
                "output": mission.output,
                "error": mission.error,
                "plan": mission.plan,
                "tool_calls": mission.tool_calls or [],
                "tokens_used": mission.tokens_used or 0,
                "created_at": mission.created_at.isoformat() if mission.created_at else None,
                "completed_at": mission.completed_at.isoformat() if mission.completed_at else None,
                "duration_ms": mission.duration_ms or 0,
            }

    async def cancel(self, mission_id: str, workspace_id: str):
        async with self.session_maker() as session:
            mission = await session.get(MissionModel, mission_id)
            if mission and mission.workspace_id == workspace_id:
                mission.status = "cancelled"
                await session.commit()

    async def list_missions(self, workspace_id: str, limit: int = 50) -> List[Dict]:
        async with self.session_maker() as session:
            result = await session.execute(
                select(MissionModel)
                .where(MissionModel.workspace_id == workspace_id)
                .order_by(MissionModel.created_at.desc())
                .limit(limit)
            )
            return [
                {
                    "id": m.id,
                    "status": m.status,
                    "prompt": m.prompt[:200] + "..." if len(m.prompt) > 200 else m.prompt,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in result.scalars()
            ]

    async def _is_cancelled(self, mission_id: str, workspace_id: str) -> bool:
        async with self.session_maker() as session:
            mission = await session.get(MissionModel, mission_id)
            return mission is not None and mission.status == "cancelled"

    async def _execute_step(self, todo: Dict, workspace_id: str, mission_id: str, model: Optional[str], step_index: int) -> Dict:
        tool_name = todo.get("tool")
        task = todo.get("task", "")

        step_output = ""
        tool_calls = []
        tokens_used = 0

        if tool_name and tool_name in self.tools.tools:
            # Execute tool
            try:
                tool_result = await self.tools.invoke(tool_name, {"query": task}, workspace_id)
                step_output = f"Tool `{tool_name}` result:\n{json.dumps(tool_result, indent=2, default=str)[:2000]}"
                tool_calls.append({"tool": tool_name, "input": task, "status": "ok"})
            except Exception as e:
                step_output = f"Tool `{tool_name}` failed: {str(e)}"
                tool_calls.append({"tool": tool_name, "input": task, "status": "error", "error": str(e)})

        else:
            # Direct LLM call
            try:
                messages = [
                    {"role": "system", "content": "You are a helpful assistant. Be concise."},
                    {"role": "user", "content": task},
                ]

                resp = await self.client.post(
                    f"{self.router_url}/v1/chat/completions",
                    headers={
                        "X-Workspace-ID": workspace_id,
                        "Authorization": "Bearer tricore-local-dev-key",
                    },
                    json={
                        "model": model or self.default_model,
                        "messages": messages,
                        "temperature": 0.7,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                step_output = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                tokens_used = usage.get("total_tokens", 0)

            except Exception as e:
                step_output = f"LLM call failed: {str(e)}"

        # Ingest conversation to memory
        await self.memory.ingest_conversation(workspace_id, mission_id, step_index, task)

        return {
            "output": step_output,
            "tool_calls": tool_calls,
            "tokens_used": tokens_used,
        }

    async def close(self):
        if self.engine:
            await self.engine.dispose()
        if self.client:
            await self.client.aclose()
