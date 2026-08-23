"""Unit tests for Multi-Agent Swarm Orchestrator."""

import pytest
from agents.swarm import AgentSwarm, SwarmStep


@pytest.mark.asyncio
async def test_swarm_mission_lifecycle():
    swarm = AgentSwarm(max_retries=2)
    res = await swarm.run_swarm_mission("Refactor auth token expiration logic")
    assert res["status"] == "completed"
    assert res["total_steps"] == 3
    assert len(res["trace"]) == 3
    for entry in res["trace"]:
        assert entry["approved"] is True


@pytest.mark.asyncio
async def test_swarm_step_decomposition():
    swarm = AgentSwarm()
    plan = await swarm.architect.plan("Implement Prometheus scrape endpoint")
    assert len(plan) == 3
    assert plan[0].assigned_role == "architect"
    assert plan[1].assigned_role == "coder"
    assert plan[2].assigned_role == "reviewer"
