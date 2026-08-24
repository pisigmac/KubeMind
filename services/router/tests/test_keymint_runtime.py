from datetime import datetime, timedelta, timezone

import httpx
import pytest

from router.keymint_runtime import (
    CapabilityBinding,
    CapabilityGrant,
    HttpKeyMintRuntimeClient,
    KeyMintConfig,
    KeyMintConnection,
    KeyMintRuntimeError,
)


def config(**overrides):
    values = {
        "base_url": "https://keymint.internal.example",
        "audience": "keymint-provider-proxy",
        "issue_timeout_seconds": 2,
        "proxy_timeout_seconds": 20,
        "revoke_timeout_seconds": 2,
    }
    values.update(overrides)
    return KeyMintConfig.from_mapping(values, environ={})


def connection():
    return KeyMintConnection(
        connection_ref="conn_provider001",
        workspace_id="ws_test001",
        provider="openai",
        data_region="global",
        virtual_key_id="018f47d2-3ca2-7c63-a58f-55aa3a650001",
        control_authorization="Bearer control-top-secret",
        proxy_authorization="Bearer proxy-top-secret",
    )


def binding(**overrides):
    values = {
        "workspace_id": "ws_test001",
        "project_id": "project_test001",
        "run_id": "run_test001",
        "model": "gpt-4o-mini",
        "operation": "chat.completions",
        "audience": "keymint-provider-proxy",
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=1),
        "max_cost_micros": 500,
    }
    values.update(overrides)
    return CapabilityBinding(**values)


@pytest.mark.asyncio
async def test_http_client_issues_one_use_scope_calls_proxy_and_revokes():
    seen = []
    expected_expiry = binding().expires_at

    async def handler(request):
        seen.append(request)
        if request.url.path.endswith("/capabilities"):
            body = __import__("json").loads(request.content)
            assert request.headers["authorization"] == "Bearer control-top-secret"
            assert body == {
                "operations": ["chat.completions"],
                "models": ["gpt-4o-mini"],
                "expires_at": expected_expiry.isoformat().replace("+00:00", "Z"),
                "max_uses": 1,
                "max_cost_micros": 500,
            }
            return httpx.Response(
                201,
                json={
                    "id": "cap_123",
                    "token": "kmcap_scoped-token-value-long-enough",
                    "run_id": "keymint-run-123",
                    "operations": ["chat.completions"],
                    "models": ["gpt-4o-mini"],
                    "expires_at": expected_expiry.isoformat().replace("+00:00", "Z"),
                    "max_uses": 1,
                    "max_cost_micros": 500,
                },
            )
        if request.url.path.endswith("/proxy/chat/completions"):
            assert request.headers["authorization"] == "Bearer proxy-top-secret"
            assert request.headers["x-keymint-capability"] == "kmcap_scoped-token-value-long-enough"
            assert request.headers["x-keymint-run-id"] == "keymint-run-123"
            assert "control-top-secret" not in request.content.decode()
            return httpx.Response(200, json={"choices": [], "usage": {}})
        assert request.url.path.endswith("/capabilities/cap_123/revoke")
        assert request.headers["authorization"] == "Bearer control-top-secret"
        return httpx.Response(200, json={"status": "revoked"})

    client = HttpKeyMintRuntimeClient(config(), transport=httpx.MockTransport(handler))
    scope = binding(expires_at=expected_expiry)
    grant = await client.issue(connection(), scope)
    result = await client.chat(
        connection(), grant, {"model": "gpt-4o-mini", "messages": []}
    )
    await client.revoke(connection(), grant.capability_id)
    await client.close()

    assert result == {"choices": [], "usage": {}}
    assert len(seen) == 3


@pytest.mark.asyncio
async def test_denied_revoked_or_expired_capability_returns_only_safe_code():
    async def denied(_request):
        return httpx.Response(403, text="provider body with proxy-top-secret and prompt")

    client = HttpKeyMintRuntimeClient(config(), transport=httpx.MockTransport(denied))
    grant = CapabilityGrant(
        capability_id="cap_123",
        token="kmcap_scoped-token-value-long-enough",
        keymint_run_id="keymint-run-123",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    with pytest.raises(KeyMintRuntimeError) as raised:
        await client.chat(connection(), grant, {"messages": [{"content": "private"}]})
    assert str(raised.value) == "CAPABILITY_DENIED"
    assert "private" not in str(raised.value)
    assert "proxy-top-secret" not in str(raised.value)

    expired = CapabilityGrant(
        capability_id="cap_123",
        token="kmcap_scoped-token-value-long-enough",
        keymint_run_id="keymint-run-123",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    with pytest.raises(KeyMintRuntimeError, match="CAPABILITY_EXPIRED"):
        await client.chat(connection(), expired, {"messages": []})
    await client.close()


@pytest.mark.asyncio
async def test_revocation_failure_is_typed_and_secret_safe():
    async def unavailable(_request):
        return httpx.Response(503, text="database details control-top-secret")

    client = HttpKeyMintRuntimeClient(config(), transport=httpx.MockTransport(unavailable))
    with pytest.raises(KeyMintRuntimeError) as raised:
        await client.revoke(connection(), "cap_123")
    assert raised.value.code == "CAPABILITY_REVOKE_FAILED"
    assert raised.value.retryable is True
    assert "secret" not in str(raised.value)
    await client.close()


def test_config_and_connection_repr_are_fail_closed_and_redacted():
    assert "top-secret" not in repr(connection())
    resolved = KeyMintConfig.from_mapping(
        {
            "base_url": "${KEYMINT_URL}",
            "audience": "${KEYMINT_AUDIENCE}",
            "issue_timeout_seconds": "${KEYMINT_ISSUE_TIMEOUT}",
            "proxy_timeout_seconds": "${KEYMINT_PROXY_TIMEOUT}",
            "revoke_timeout_seconds": "${KEYMINT_REVOKE_TIMEOUT}",
        },
        environ={
            "KEYMINT_URL": "https://keymint.example",
            "KEYMINT_AUDIENCE": "keymint-provider-proxy",
            "KEYMINT_ISSUE_TIMEOUT": "1",
            "KEYMINT_PROXY_TIMEOUT": "10",
            "KEYMINT_REVOKE_TIMEOUT": "1",
        },
    )
    assert resolved.base_url == "https://keymint.example"

    for invalid in (
        {"base_url": "http://keymint.example"},
        {"audience": "attacker-audience"},
        {"proxy_timeout_seconds": 0},
    ):
        with pytest.raises(KeyMintRuntimeError, match="CAPABILITY_CONFIG_INVALID"):
            config(**invalid)
