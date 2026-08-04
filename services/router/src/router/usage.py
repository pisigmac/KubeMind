import os
from datetime import datetime
from typing import Dict, Any

from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class UsageRecord(Base):
    __tablename__ = "router_usage"
    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(String, index=True)
    provider = Column(String)
    model = Column(String)
    requests = Column(Integer, default=0)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class UsageTracker:
    def __init__(self):
        self.engine = None
        self.session_maker = None

    async def init(self):
        db_url = os.environ.get("DATABASE_URL", "postgresql://tricore:tricore@localhost:5432/tricore")
        async_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        self.engine = create_async_engine(async_url, echo=False)

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self.session_maker = async_sessionmaker(self.engine, expire_on_commit=False)
        print("[SwitchBoard] Usage tracker initialized")

    async def record(self, workspace_id: str, provider: str, model: str, usage: Dict[str, int]):
        if not self.session_maker:
            return

        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

        # Rough cost calculation
        cost = (total_tokens * 0.0000015)  # Conservative estimate

        async with self.session_maker() as session:
            record = UsageRecord(
                workspace_id=workspace_id,
                provider=provider,
                model=model,
                requests=1,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost=cost,
            )
            session.add(record)
            await session.commit()

    async def get_summary(self, workspace_id: str) -> Dict[str, Any]:
        if not self.session_maker:
            return {"workspace_id": workspace_id, "total_requests": 0, "total_tokens": 0, "estimated_cost": 0.0}

        async with self.session_maker() as session:
            from sqlalchemy import func, select
            stmt = select(
                func.count().label("total_requests"),
                func.coalesce(func.sum(UsageRecord.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(UsageRecord.estimated_cost), 0.0).label("estimated_cost"),
            ).where(UsageRecord.workspace_id == workspace_id)

            result = await session.execute(stmt)
            row = result.one()

            # Provider breakdown
            breakdown_stmt = select(
                UsageRecord.provider,
                func.count().label("requests"),
                func.coalesce(func.sum(UsageRecord.total_tokens), 0).label("tokens"),
                func.coalesce(func.sum(UsageRecord.estimated_cost), 0.0).label("cost"),
            ).where(UsageRecord.workspace_id == workspace_id).group_by(UsageRecord.provider)

            breakdown_result = await session.execute(breakdown_stmt)
            providers = {
                r.provider: {"requests": r.requests, "tokens": r.tokens, "cost": r.cost}
                for r in breakdown_result.all()
            }

            return {
                "workspace_id": workspace_id,
                "total_requests": row.total_requests,
                "total_tokens": row.total_tokens,
                "estimated_cost": row.estimated_cost,
                "providers": providers,
            }

    async def close(self):
        if self.engine:
            await self.engine.dispose()
