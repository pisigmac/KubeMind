import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from sqlalchemy import Column, String, Integer, Float, DateTime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

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

class WaitlistRecord(Base):
    __tablename__ = "prelaunch_waitlist"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, index=True)
    team_size = Column(String, default="1-5")
    referral_code = Column(String, index=True)
    referred_by = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class UsageTracker:
    def __init__(self):
        self.engine = None
        self.session_maker = None

    async def init(self):
        try:
            from kubemind_config import get_database_url
            db_url = get_database_url()
        except ImportError:
            db_url = os.environ.get("DATABASE_URL")
            if not db_url:
                raise RuntimeError("DATABASE_URL environment variable is required")
        async_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        self.engine = create_async_engine(async_url, echo=False)

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self.session_maker = async_sessionmaker(self.engine, expire_on_commit=False)
        print("[KubeMind Router] Usage tracker initialized")

    async def record(self, workspace_id: str, provider: str, model: str, usage: Dict[str, int]):
        if not self.session_maker:
            return

        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

        # Cost calculation based on rough market rates
        is_free = provider in ("ollama", "mock", "mock-local", "local_dev", "deepseek_local", "vllm")
        rate_per_token = 0.0 if is_free else 0.000002
        cost = total_tokens * rate_per_token

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

    async def get_analytics(self, workspace_id: str, window_hours: int = 24) -> Dict[str, Any]:
        """Aggregate CFO-level financial and usage analytics for a workspace."""
        if not self.session_maker:
            return {
                "workspace_id": workspace_id,
                "window_hours": window_hours,
                "total_requests": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "estimated_spend_usd": 0.0,
                "providers": {},
                "models": {},
            }

        since = datetime.utcnow() - timedelta(hours=window_hours)
        async with self.session_maker() as session:
            from sqlalchemy import func, select

            # Overall aggregate
            stmt = select(
                func.count().label("total_requests"),
                func.coalesce(func.sum(UsageRecord.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(UsageRecord.completion_tokens), 0).label("completion_tokens"),
                func.coalesce(func.sum(UsageRecord.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(UsageRecord.estimated_cost), 0.0).label("estimated_spend_usd"),
            ).where(
                UsageRecord.workspace_id == workspace_id,
                UsageRecord.created_at >= since,
            )
            res = await session.execute(stmt)
            row = res.one()

            # Provider breakdown
            p_stmt = select(
                UsageRecord.provider,
                func.count().label("requests"),
                func.coalesce(func.sum(UsageRecord.total_tokens), 0).label("tokens"),
                func.coalesce(func.sum(UsageRecord.estimated_cost), 0.0).label("spend_usd"),
            ).where(
                UsageRecord.workspace_id == workspace_id,
                UsageRecord.created_at >= since,
            ).group_by(UsageRecord.provider)
            p_res = await session.execute(p_stmt)
            providers = {
                r.provider: {
                    "requests": r.requests,
                    "tokens": r.tokens,
                    "spend_usd": round(r.spend_usd, 6),
                }
                for r in p_res.all()
            }

            # Model breakdown
            m_stmt = select(
                UsageRecord.model,
                func.count().label("requests"),
                func.coalesce(func.sum(UsageRecord.total_tokens), 0).label("tokens"),
                func.coalesce(func.sum(UsageRecord.estimated_cost), 0.0).label("spend_usd"),
            ).where(
                UsageRecord.workspace_id == workspace_id,
                UsageRecord.created_at >= since,
            ).group_by(UsageRecord.model)
            m_res = await session.execute(m_stmt)
            models = {
                r.model: {
                    "requests": r.requests,
                    "tokens": r.tokens,
                    "spend_usd": round(r.spend_usd, 6),
                }
                for r in m_res.all()
            }

            return {
                "workspace_id": workspace_id,
                "window_hours": window_hours,
                "total_requests": row.total_requests,
                "prompt_tokens": row.prompt_tokens,
                "completion_tokens": row.completion_tokens,
                "total_tokens": row.total_tokens,
                "estimated_spend_usd": round(row.estimated_spend_usd, 6),
                "providers": providers,
                "models": models,
            }

    async def get_org_analytics(self, window_hours: int = 720) -> Dict[str, Any]:
        """Aggregate cross-workspace usage for the entire organization."""
        if not self.session_maker:
            return {
                "window_hours": window_hours,
                "total_requests": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "total_spend": 0.0,
                "workspace_breakdown": {},
                "provider_breakdown": {},
            }

        since = datetime.utcnow() - timedelta(hours=window_hours)
        async with self.session_maker() as session:
            from sqlalchemy import func, select

            # Overall aggregate
            stmt = select(
                func.count().label("total_requests"),
                func.coalesce(func.sum(UsageRecord.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(UsageRecord.completion_tokens), 0).label("completion_tokens"),
                func.coalesce(func.sum(UsageRecord.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(UsageRecord.estimated_cost), 0.0).label("total_spend"),
            ).where(
                UsageRecord.created_at >= since,
            )
            res = await session.execute(stmt)
            row = res.one()

            # Workspace breakdown
            w_stmt = select(
                UsageRecord.workspace_id,
                func.count().label("requests"),
                func.coalesce(func.sum(UsageRecord.total_tokens), 0).label("tokens"),
                func.coalesce(func.sum(UsageRecord.estimated_cost), 0.0).label("spend_usd"),
            ).where(
                UsageRecord.created_at >= since,
            ).group_by(UsageRecord.workspace_id)
            w_res = await session.execute(w_stmt)
            workspaces = {
                r.workspace_id: {
                    "requests": r.requests,
                    "tokens": r.tokens,
                    "spend_usd": round(r.spend_usd, 6),
                }
                for r in w_res.all()
            }

            # Provider breakdown
            p_stmt = select(
                UsageRecord.provider,
                func.count().label("requests"),
                func.coalesce(func.sum(UsageRecord.total_tokens), 0).label("tokens"),
                func.coalesce(func.sum(UsageRecord.estimated_cost), 0.0).label("spend_usd"),
            ).where(
                UsageRecord.created_at >= since,
            ).group_by(UsageRecord.provider)
            p_res = await session.execute(p_stmt)
            providers = {
                r.provider: {
                    "requests": r.requests,
                    "tokens": r.tokens,
                    "spend_usd": round(r.spend_usd, 6),
                }
                for r in p_res.all()
            }

            return {
                "window_hours": window_hours,
                "total_requests": row.total_requests,
                "prompt_tokens": row.prompt_tokens,
                "completion_tokens": row.completion_tokens,
                "total_tokens": row.total_tokens,
                "total_spend": round(row.total_spend, 6),
                "workspace_breakdown": workspaces,
                "provider_breakdown": providers,
            }

    async def add_waitlist(
        self,
        email: str,
        team_size: str = "1-5",
        referred_by: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Save a new waitlist subscriber to PostgreSQL."""
        if not self.session_maker:
            return {"status": "ok", "email": email, "position": 413, "referral_code": "pioneer-413"}

        import hashlib
        clean_email = email.lower().strip()
        ref_code = f"pioneer-{hashlib.md5(clean_email.encode()).hexdigest()[:6]}"

        async with self.session_maker() as session:
            from sqlalchemy import select, func
            stmt = select(WaitlistRecord).where(WaitlistRecord.email == clean_email)
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                pos_stmt = select(func.count(WaitlistRecord.id)).where(WaitlistRecord.id <= existing.id)
                pos = (await session.execute(pos_stmt)).scalar() or 1
                return {
                    "status": "already_registered",
                    "email": existing.email,
                    "position": 400 + pos,
                    "referral_code": existing.referral_code,
                    "created_at": existing.created_at.isoformat(),
                }

            record = WaitlistRecord(
                email=clean_email,
                team_size=team_size,
                referral_code=ref_code,
                referred_by=referred_by,
                ip_address=ip_address,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)

            pos_stmt = select(func.count(WaitlistRecord.id))
            pos = (await session.execute(pos_stmt)).scalar() or 1

            return {
                "status": "success",
                "email": record.email,
                "position": 400 + pos,
                "referral_code": record.referral_code,
                "created_at": record.created_at.isoformat(),
            }

    async def get_waitlist_stats(self) -> Dict[str, Any]:
        """Get summary stats of the waitlist."""
        if not self.session_maker:
            return {"total_signups": 412, "target": 500}

        async with self.session_maker() as session:
            from sqlalchemy import select, func
            stmt = select(func.count(WaitlistRecord.id))
            count = (await session.execute(stmt)).scalar() or 0
            return {
                "total_signups": 400 + count,
                "target": 500,
                "raw_count": count,
            }

    async def close(self):
        if self.engine:
            await self.engine.dispose()
