"""Incident Notification Webhook Dispatcher for KubeMind Sentinel.

Dispatches real-time alerting webhooks to Slack, PagerDuty, Discord, or generic
HTTPS endpoints upon security policy violations, audit tampering, or circuit breaks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import httpx


@dataclass
class IncidentEvent:
    event_type: str  # policy_violation, tamper_detected, circuit_breaker_open, budget_breach
    severity: str    # critical, high, warning, info
    workspace_id: str
    summary: str
    details: Dict[str, Any]
    timestamp: str


class WebhookDispatcher:
    """Dispatches real-time event payloads to configured webhook URLs."""

    def __init__(self, endpoints: Optional[List[str]] = None, timeout: float = 4.0):
        self.endpoints = endpoints or []
        self.timeout = timeout

    def register_endpoint(self, url: str) -> None:
        """Register a destination webhook URL."""
        if url and url not in self.endpoints:
            self.endpoints.append(url)

    def format_slack_payload(self, event: IncidentEvent) -> Dict[str, Any]:
        """Format an IncidentEvent as a Slack webhook message block."""
        icon = "🚨" if event.severity == "critical" else "⚠️"
        return {
            "text": f"{icon} *[KubeMind Alert - {event.severity.upper()}]* {event.summary}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{icon} *[KubeMind Incident: {event.event_type}]*\n*Workspace:* `{event.workspace_id}`\n*Severity:* `{event.severity}`\n*Summary:* {event.summary}",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"Timestamp: {event.timestamp} | Sentinel Security Ledger"}
                    ],
                },
            ],
        }

    async def dispatch_event(self, event: IncidentEvent) -> List[Dict[str, Any]]:
        """Dispatch incident event to all registered webhook endpoints asynchronously."""
        if not self.endpoints:
            return []

        results = []
        payload = self.format_slack_payload(event)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for url in self.endpoints:
                try:
                    resp = await client.post(url, json=payload)
                    results.append({
                        "url": url,
                        "status_code": resp.status_code,
                        "success": 200 <= resp.status_code < 300,
                    })
                except Exception as e:
                    results.append({
                        "url": url,
                        "status_code": 0,
                        "success": False,
                        "error": str(e),
                    })

        return results


_GLOBAL_DISPATCHER = WebhookDispatcher()


def get_default_webhook_dispatcher() -> WebhookDispatcher:
    return _GLOBAL_DISPATCHER
