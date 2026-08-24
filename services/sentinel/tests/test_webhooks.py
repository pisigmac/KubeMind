"""Unit tests for Sentinel Webhook Dispatcher."""

import pytest
import respx

from sentinel.webhooks import IncidentEvent, WebhookDispatcher


@pytest.mark.asyncio
@respx.mock
async def test_webhook_dispatcher_success():
    dispatcher = WebhookDispatcher(endpoints=["https://hooks.slack.com/services/T00/B00/X00"])
    route = respx.post("https://hooks.slack.com/services/T00/B00/X00").respond(200, text="ok")

    event = IncidentEvent(
        event_type="policy_violation",
        severity="critical",
        workspace_id="acme-prod",
        summary="Unauthorized private key detected and blocked",
        details={"rule": "private_key"},
        timestamp="2026-08-24T03:00:00Z",
    )

    results = await dispatcher.dispatch_event(event)

    assert len(results) == 1
    assert results[0]["success"] is True
    assert results[0]["status_code"] == 200
    assert route.called
