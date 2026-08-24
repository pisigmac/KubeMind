"""TraceLens span export integration for KubeMind Sentinel.

Converts internal KubeMind telemetry spans into TraceLens batch span payloads
and posts them to the TraceLens collector (/v1/spans).
"""
import os
from typing import Any, Dict, Optional
import httpx


def tracelens_endpoint() -> str:
    return os.environ.get("TRACELENS_ENDPOINT", os.environ.get("TRACELENS_URL", "")).rstrip("/")


def tracelens_token() -> str:
    return os.environ.get("TRACELENS_TOKEN", os.environ.get("TRACELENS_API_KEY", ""))


def enabled() -> bool:
    return bool(tracelens_endpoint())


def format_tracelens_batch(span: Dict[str, Any]) -> Dict[str, Any]:
    attrs = span.get("attributes") or {}
    trace_id = str(span.get("trace_id") or span.get("correlation_id") or "unknown-trace")
    span_id = str(span.get("span_id") or "unknown-span")
    parent_id = span.get("parent_id")

    service = str(span.get("service") or "kubemind")
    operation = str(span.get("operation") or "request")
    model = attrs.get("model") or attrs.get("llm_model")
    input_tokens = int(attrs.get("prompt_tokens") or attrs.get("input_tokens") or 0)
    output_tokens = int(attrs.get("completion_tokens") or attrs.get("output_tokens") or 0)
    cost_usd = float(attrs.get("cost") or attrs.get("cost_usd") or 0.0)
    latency_ms = int(span.get("latency_ms") or attrs.get("latency_ms") or 0)
    status = "error" if span.get("status") in ("error", "failed", 500) else "ok"
    error_msg = span.get("error_message") or attrs.get("error")

    return {
        "trace_id": trace_id,
        "spans": [
            {
                "span_id": span_id,
                "parent_id": parent_id,
                "agent_type": service,
                "tool_name": operation,
                "llm_model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": latency_ms,
                "status": status,
                "error_message": str(error_msg) if error_msg else None,
                "cost_usd": cost_usd,
                "attributes": attrs,
            }
        ],
    }


class TraceLensExporter:
    def __init__(self, endpoint: Optional[str] = None, token: Optional[str] = None):
        self.endpoint = (endpoint or tracelens_endpoint()).rstrip("/")
        self.token = token or tracelens_token()
        self.client: Optional[httpx.AsyncClient] = None

    async def export_span(self, span: Dict[str, Any]) -> None:
        if not self.endpoint:
            return
        payload = format_tracelens_batch(span)
        try:
            if self.client is None:
                self.client = httpx.AsyncClient(timeout=3.0)
            headers = {"Content-Type": "application/json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            url = f"{self.endpoint}/v1/spans"
            await self.client.post(url, json=payload, headers=headers)
        except Exception as e:
            # Best effort export; log warning without failing main request flow
            print(f"[sentinel] TraceLens export error: {e}")

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None
