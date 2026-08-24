"""Optional OTLP HTTP span export (no-op when endpoint unset)."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx

_client: Optional[httpx.AsyncClient] = None


def otlp_endpoint() -> str:
    return os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").rstrip("/")


def enabled() -> bool:
    return bool(otlp_endpoint())


async def export_span(span: Dict[str, Any]) -> None:
    """Best-effort export; never raises to callers."""
    global _client
    base = otlp_endpoint()
    if not base:
        return
    try:
        if _client is None:
            _client = httpx.AsyncClient(timeout=3.0)
        # Minimal OTLP-ish JSON payload (compatible with many collectors in loose mode)
        payload = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {
                                "key": "service.name",
                                "value": {"stringValue": span.get("service", "sentinel")},
                            }
                        ]
                    },
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": str(span.get("trace_id", "")),
                                    "spanId": str(span.get("span_id", "")),
                                    "name": span.get("operation", "span"),
                                    "attributes": [
                                        {
                                            "key": "workspace_id",
                                            "value": {
                                                "stringValue": str(
                                                    span.get("workspace_id", "default")
                                                )
                                            },
                                        }
                                    ],
                                }
                            ]
                        }
                    ],
                }
            ]
        }
        url = f"{base}/v1/traces" if not base.endswith("/v1/traces") else base
        await _client.post(url, json=payload)
    except Exception:
        pass


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
