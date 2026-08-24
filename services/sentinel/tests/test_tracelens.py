import pytest
from sentinel.tracelens import TraceLensExporter, format_tracelens_batch


class TestTraceLensExporter:
    def test_format_tracelens_batch(self):
        span_payload = {
            "trace_id": "km-trace-123",
            "span_id": "span-456",
            "parent_id": None,
            "service": "router",
            "operation": "chat_completion",
            "workspace_id": "acme",
            "status": "ok",
            "latency_ms": 250,
            "attributes": {
                "model": "gpt-4o",
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "cost": 0.005,
                "intent": "code",
            },
        }
        batch = format_tracelens_batch(span_payload)
        assert batch["trace_id"] == "km-trace-123"
        assert len(batch["spans"]) == 1
        s = batch["spans"][0]
        assert s["span_id"] == "span-456"
        assert s["agent_type"] == "router"
        assert s["tool_name"] == "chat_completion"
        assert s["llm_model"] == "gpt-4o"
        assert s["input_tokens"] == 100
        assert s["output_tokens"] == 50
        assert s["cost_usd"] == 0.005
        assert s["status"] == "ok"

    @pytest.mark.asyncio
    async def test_export_span_sends_post(self, respx_mock):
        exporter = TraceLensExporter(endpoint="http://tracelens:8080", token="secret-token")
        route = respx_mock.post("http://tracelens:8080/v1/spans").respond(status_code=201, json={"ingested": 1, "trace_id": "km-trace-123"})

        span = {
            "trace_id": "km-trace-123",
            "span_id": "span-456",
            "service": "router",
            "operation": "route",
            "workspace_id": "acme",
            "status": "ok",
            "attributes": {"model": "claude-3-5-sonnet"},
        }
        await exporter.export_span(span)
        assert route.called
        req = route.calls.last.request
        assert req.headers["authorization"] == "Bearer secret-token"
        await exporter.close()
