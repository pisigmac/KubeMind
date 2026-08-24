"""The tracer client other services embed.

These previously mocked port 8083 while the client defaults to 9083, so every
request fell through to a real socket, was refused, and the resulting
`enabled = False` looked like a client bug. The URL is now set explicitly
rather than inherited from a default the test cannot see.
"""

import httpx
import pytest
import respx

from sentinel.client import TracerClient

BASE = "http://sentinel.test:8083"


@pytest.fixture(autouse=True)
def sentinel_url(monkeypatch):
    monkeypatch.setenv("SENTINEL_URL", BASE)
    monkeypatch.delenv("KUBEMIND_SERVICE_KEY", raising=False)


@pytest.fixture
def healthy():
    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{BASE}/health").mock(return_value=httpx.Response(200))
        mock.post(f"{BASE}/v1/spans").mock(return_value=httpx.Response(200))
        yield mock


class TestInit:
    @pytest.mark.asyncio
    async def test_init_success(self, healthy):
        client = TracerClient(service_name="test")
        await client.init()
        assert client.enabled is True
        await client.close()

    @pytest.mark.asyncio
    async def test_init_failure_disables_tracing(self):
        with respx.mock:
            respx.get(f"{BASE}/health").mock(return_value=httpx.Response(500))
            client = TracerClient(service_name="test")
            await client.init()
            assert client.enabled is False
            await client.close()

    @pytest.mark.asyncio
    async def test_unreachable_sentinel_does_not_raise(self):
        with respx.mock:
            respx.get(f"{BASE}/health").mock(side_effect=httpx.ConnectError("down"))
            client = TracerClient(service_name="test")
            await client.init()
            assert client.enabled is False
            await client.close()


class TestBuffering:
    @pytest.mark.asyncio
    async def test_log_span_buffers(self, healthy):
        client = TracerClient(service_name="test")
        await client.init()
        await client.log_span(
            {"trace_id": "t1", "span_id": "s1", "workspace_id": "default", "operation": "test"}
        )
        assert len(client._buffer) == 1
        await client.close()

    @pytest.mark.asyncio
    async def test_span_is_enriched_with_defaults(self, healthy):
        client = TracerClient(service_name="test")
        await client.init()
        await client.log_span({"workspace_id": "default", "operation": "test"})
        span = client._buffer[0]
        assert span["service"] == "test"
        assert span["span_id"] and span["trace_id"] and span["start_time"]
        await client.close()

    @pytest.mark.asyncio
    async def test_buffer_flushes_when_full(self, healthy, monkeypatch):
        monkeypatch.setenv("TRACER_BUFFER_SIZE", "3")
        client = TracerClient(service_name="test")
        await client.init()
        for i in range(3):
            await client.log_span({"span_id": f"s{i}", "workspace_id": "w", "operation": "t"})
        assert client._buffer == []
        await client.close()

    @pytest.mark.asyncio
    async def test_disabled_client_does_not_buffer(self):
        with respx.mock:
            respx.get(f"{BASE}/health").mock(return_value=httpx.Response(500))
            client = TracerClient(service_name="test")
            await client.init()
            await client.log_span({"span_id": "s1", "workspace_id": "w", "operation": "t"})
            assert client._buffer == []
            await client.close()

    @pytest.mark.asyncio
    async def test_close_flushes_remaining_spans(self):
        with respx.mock:
            respx.get(f"{BASE}/health").mock(return_value=httpx.Response(200))
            route = respx.post(f"{BASE}/v1/spans").mock(
                return_value=httpx.Response(200)
            )
            client = TracerClient(service_name="test")
            await client.init()
            await client.log_span(
                {"span_id": "s1", "workspace_id": "w", "operation": "t"}
            )
            # Buffered spans must not be lost on shutdown.
            await client.close()
            assert route.called


class TestSpanHelpers:
    @pytest.mark.asyncio
    async def test_log_llm_call(self, healthy):
        client = TracerClient(service_name="test")
        await client.init()
        await client.log_llm_call("ws1", "ollama", "llama3.1", 10, 5, 150.0)
        span = client._buffer[0]
        assert span["operation"] == "llm_call"
        assert span["attributes"]["provider"] == "ollama"
        assert span["attributes"]["total_tokens"] == 15
        await client.close()

    @pytest.mark.asyncio
    async def test_log_tool_call(self, healthy):
        client = TracerClient(service_name="test")
        await client.init()
        await client.log_tool_call("ws1", "filesystem", 50.0, status="ok")
        span = client._buffer[0]
        assert span["operation"] == "tool_call"
        assert span["attributes"]["tool"] == "filesystem"
        await client.close()

    @pytest.mark.asyncio
    async def test_log_request(self, healthy):
        client = TracerClient(service_name="test")
        await client.init()
        await client.log_request("ws1", "route", 12.0)
        assert client._buffer[0]["operation"] == "route"
        await client.close()


class TestServiceAuth:
    @pytest.mark.asyncio
    async def test_flush_sends_the_service_key(self, monkeypatch):
        monkeypatch.setenv("KUBEMIND_SERVICE_KEY", "svc-secret")
        seen = {}

        def capture(request):
            seen["api_key"] = request.headers.get("X-API-Key")
            seen["workspace"] = request.headers.get("X-Workspace-ID")
            return httpx.Response(200)

        with respx.mock:
            respx.get(f"{BASE}/health").mock(return_value=httpx.Response(200))
            respx.post(f"{BASE}/v1/spans").mock(side_effect=capture)

            client = TracerClient(service_name="test")
            await client.init()
            await client.log_span(
                {"span_id": "s1", "workspace_id": "acme", "operation": "t"}
            )
            await client.close()

        # Sentinel binds the entry to this workspace only because the caller
        # proved it is a KubeMind service.
        assert seen["api_key"] == "svc-secret"
        assert seen["workspace"] == "acme"

    @pytest.mark.asyncio
    async def test_no_key_configured_sends_no_header(self):
        seen = {}

        def capture(request):
            seen["api_key"] = request.headers.get("X-API-Key")
            return httpx.Response(200)

        with respx.mock:
            respx.get(f"{BASE}/health").mock(return_value=httpx.Response(200))
            respx.post(f"{BASE}/v1/spans").mock(side_effect=capture)
            client = TracerClient(service_name="test")
            await client.init()
            await client.log_span({"span_id": "s1", "workspace_id": "w", "operation": "t"})
            await client.close()

        assert seen["api_key"] is None
