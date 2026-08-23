"""Unit tests for Cross-Cluster Cache Replicator in Router."""

import pytest
import respx

from router.cache.replication import DistributedCacheReplicator


@pytest.mark.asyncio
@respx.mock
async def test_distributed_cache_replicator_flush():
    replicator = DistributedCacheReplicator(
        current_region="us-east-1",
        peer_endpoints=["https://eu-west-1.kubemind.internal"],
    )
    route = respx.post("https://eu-west-1.kubemind.internal/v1/cache/replicate").respond(200, json={"synced": 1})

    replicator.queue_replication(
        workspace_id="acme",
        signature="sig-123",
        partition="code",
        model="llama3.1",
        intent="code",
        prompt_preview="def parse_yaml(): ...",
        embedding=[0.1] * 768,
        response={"choices": [{"message": {"content": "import yaml"}}]},
    )

    results = await replicator.flush_replication_queue()

    assert len(results) == 1
    assert results[0]["success"] is True
    assert route.called
