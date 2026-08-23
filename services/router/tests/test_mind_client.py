import httpx
import pytest
import respx

from router.mind_client import (
    STATUS_EMPTY,
    STATUS_UNAVAILABLE,
    STATUS_USED,
    MindClient,
)


@pytest.mark.asyncio
async def test_retrieve_used_attaches_context():
    client = MindClient(base_url="http://mind.test")
    client.client = httpx.AsyncClient()
    with respx.mock:
        respx.post("http://mind.test/v1/query").mock(
            return_value=httpx.Response(
                200,
                json={"results": [{"content": "policy text", "id": "n1"}]},
            )
        )
        out = await client.retrieve("what is the policy", "acme")
    await client.close()
    assert out.status == STATUS_USED
    assert out.used is True
    assert "policy text" in out.context


@pytest.mark.asyncio
async def test_retrieve_empty_corpus():
    client = MindClient(base_url="http://mind.test")
    client.client = httpx.AsyncClient()
    with respx.mock:
        respx.post("http://mind.test/v1/query").mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        out = await client.retrieve("unknown", "acme")
    await client.close()
    assert out.status == STATUS_EMPTY
    assert out.used is False


@pytest.mark.asyncio
async def test_retrieve_outage_is_unavailable_not_empty():
    client = MindClient(base_url="http://mind.test")
    client.client = httpx.AsyncClient()
    with respx.mock:
        respx.post("http://mind.test/v1/query").mock(
            return_value=httpx.Response(503, json={"detail": "down"})
        )
        out = await client.retrieve("unknown", "acme")
    await client.close()
    assert out.status == STATUS_UNAVAILABLE


@pytest.mark.asyncio
async def test_disabled_client_is_unavailable():
    client = MindClient(base_url="http://mind.test")
    client.enabled = False
    client.client = httpx.AsyncClient()
    out = await client.retrieve("q", "acme")
    await client.close()
    assert out.status == STATUS_UNAVAILABLE
