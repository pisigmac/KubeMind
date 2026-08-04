import pytest
import httpx
import respx
from sentinel.client import TracerClient

class TestTracerClient:
    @pytest.mark.asyncio
    async def test_init_success(self):
        with respx.mock:
            respx.get("http://localhost:8083/health").mock(
                return_value=httpx.Response(200, json={"status": "ok"})
            )
            client = TracerClient(service_name="test")
            await client.init()
            assert client.enabled is True
            await client.close()

    @pytest.mark.asyncio
    async def test_init_failure(self):
        with respx.mock:
            respx.get("http://localhost:8083/health").mock(
                return_value=httpx.Response(500)
            )
            client = TracerClient(service_name="test")
            await client.init()
            assert client.enabled is False
            await client.close()

    @pytest.mark.asyncio
    async def test_log_span(self):
        with respx.mock:
            respx.get("http://localhost:8083/health").mock(return_value=httpx.Response(200))
            respx.post("http://localhost:8083/v1/spans").mock(return_value=httpx.Response(200))

            client = TracerClient(service_name="test")
            await client.init()

            await client.log_span({
                "trace_id": "t1",
                "span_id": "s1",
                "workspace_id": "default",
                "operation": "test",
            })
            assert len(client._buffer) == 1
            await client.close()

    @pytest.mark.asyncio
    async def test_log_llm_call(self):
        with respx.mock:
            respx.get("http://localhost:8083/health").mock(return_value=httpx.Response(200))
            respx.post("http://localhost:8083/v1/spans").mock(return_value=httpx.Response(200))

            client = TracerClient(service_name="test")
            await client.init()

            await client.log_llm_call("ws1", "ollama", "llama3.1", 10, 5, 150.0)
            assert len(client._buffer) == 1
            span = client._buffer[0]
            assert span["service"] == "test"
            assert span["operation"] == "llm_call"
            assert span["attributes"]["provider"] == "ollama"
            await client.close()

    @pytest.mark.asyncio
    async def test_log_tool_call(self):
        with respx.mock:
            respx.get("http://localhost:8083/health").mock(return_value=httpx.Response(200))
            respx.post("http://localhost:8083/v1/spans").mock(return_value=httpx.Response(200))

            client = TracerClient(service_name="test")
            await client.init()

            await client.log_tool_call("ws1", "filesystem", 50.0, status="ok")
            span = client._buffer[0]
            assert span["operation"] == "tool_call"
            assert span["attributes"]["tool"] == "filesystem"
            await client.close()
