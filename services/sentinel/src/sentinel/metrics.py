"""In-process Prometheus-style counters for sentinel."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Dict, Tuple

_lock = threading.Lock()
_spans_total: Dict[Tuple[str, str], int] = defaultdict(int)  # (service, status)
_redactions_total = 0
_injection_flagged_total = 0


def record_span(service: str, status: str) -> None:
    with _lock:
        _spans_total[(service or "unknown", status or "ok")] += 1


def record_redaction(count: int = 1) -> None:
    global _redactions_total
    with _lock:
        _redactions_total += count


def record_injection_flagged() -> None:
    global _injection_flagged_total
    with _lock:
        _injection_flagged_total += 1


def render_prometheus(websocket_connections: int = 0) -> str:
    lines = [
        "# HELP kubemind_spans_ingested_total Spans ingested by sentinel",
        "# TYPE kubemind_spans_ingested_total counter",
    ]
    with _lock:
        for (service, status), n in sorted(_spans_total.items()):
            lines.append(
                f'kubemind_spans_ingested_total{{service="{service}",status="{status}"}} {n}'
            )
        lines.append("# HELP kubemind_redactions_total Redaction events applied")
        lines.append("# TYPE kubemind_redactions_total counter")
        lines.append(f"kubemind_redactions_total {_redactions_total}")
        lines.append("# HELP kubemind_injection_flagged_total Spans with injection flags")
        lines.append("# TYPE kubemind_injection_flagged_total counter")
        lines.append(f"kubemind_injection_flagged_total {_injection_flagged_total}")
        lines.append("# HELP kubemind_websocket_connections Active WS connections")
        lines.append("# TYPE kubemind_websocket_connections gauge")
        lines.append(f"kubemind_websocket_connections {websocket_connections}")
    return "\n".join(lines) + "\n"
