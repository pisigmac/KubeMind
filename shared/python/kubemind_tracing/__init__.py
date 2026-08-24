"""Lightweight correlation ID propagation for KubeMind services."""
import uuid
from typing import Dict

CORRELATION_HEADER = "x-correlation-id"
TRACEPARENT_HEADER = "traceparent"


def generate_correlation_id() -> str:
    return f"km-{uuid.uuid4()}"


def extract_correlation_id(headers: Dict[str, str]) -> str:
    if CORRELATION_HEADER in headers:
        return headers[CORRELATION_HEADER]
    if TRACEPARENT_HEADER in headers:
        parts = headers[TRACEPARENT_HEADER].split("-")
        if len(parts) >= 2:
            return parts[1]
    return generate_correlation_id()
