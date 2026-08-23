import asyncio
import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from router.keymint_runtime import (
    CapabilityGrant,
    KeyMintConnection,
    KeyMintRuntimeError,
)
from router.zetakube_runtime import (
    InMemoryTerminalResultStore,
    TrustedRuntimeScope,
    ZetakubeRuntimeAdapter,
)


FIXTURE = Path(__file__).parent / "fixtures" / "zetakube-runtime" / "command-envelope.v1.json"
ROUTING_GOLDEN = (
    Path(__file__).parent
    / "fixtures"
    / "zetakube-runtime"
    / "routing-golden.v1.json"
)


def canonical_deadline(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Cancellation:
    def __init__(self):
        self.event = asyncio.Event()

    def is_cancelled(self):
        return self.event.is_set()

    async def wait(self):
        await self.event.wait()

    def cancel(self):
        self.event.set()


class Provider:
    def __init__(self, response=None, error=None, name="openai"):
        self.name = name
        self.response = response or {
            "id": "req_123",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "safe answer"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 7, "completion_tokens": 3},
        }
        self.error = error
        self.calls = 0

    async def chat(self, request):
        self.calls += 1
        if self.error:
            raise self.error
        return copy.deepcopy(self.response)

    def estimate_cost(self, input_tokens, output_tokens):
        return 0.000010


class Registry:
    def __init__(self, providers):
        self.providers = providers
        self.seen_pool = None

    def eligible_providers(self, model, *, pool, policy, keymint_managed=False):
        self.seen_pool = tuple(pool)
        assert keymint_managed is True
        return [p for p in self.providers if p.name in pool]

    async def health_check_all(self):
        return [
            {"name": p.name, "healthy": True, "internal": "must-not-leak"}
            for p in self.providers
        ]


class ConnectionResolver:
    def __init__(self, connection=None, error=None):
        self.connection = connection or KeyMintConnection(
            connection_ref="conn_provider001",
            workspace_id="ws_test001",
            provider="openai",
            data_region="global",
            virtual_key_id="018f47d2-3ca2-7c63-a58f-55aa3a650001",
            control_authorization="Bearer control-secret",
            proxy_authorization="Bearer proxy-secret",
        )
        self.error = error
        self.calls = []

    async def resolve(self, connection_ref, workspace_id):
        self.calls.append((connection_ref, workspace_id))
        if self.error:
            raise self.error
        return self.connection


class KeyMintClient:
    def __init__(self, provider, *, issue_error=None, chat_error=None, revoke_error=None):
        self.provider = provider
        self.issue_error = issue_error
        self.chat_error = chat_error
        self.revoke_error = revoke_error
        self.bindings = []
        self.payloads = []
        self.revocations = []

    async def issue(self, connection, binding):
        self.bindings.append((connection, binding))
        if self.issue_error:
            raise self.issue_error
        return CapabilityGrant(
            capability_id="cap_123",
            token="kmcap_not-a-provider-secret",
            keymint_run_id="keymint-run-123",
            expires_at=binding.expires_at,
        )

    async def chat(self, connection, grant, payload):
        self.payloads.append((connection, grant, payload))
        if self.chat_error:
            raise self.chat_error
        return await self.provider.chat(payload)

    async def revoke(self, connection, capability_id):
        self.revocations.append((connection.connection_ref, capability_id))
        if self.revoke_error:
            raise self.revoke_error


@pytest.fixture
def command():
    value = json.loads(FIXTURE.read_text())
    value["deadline"] = canonical_deadline(datetime.now(timezone.utc) + timedelta(seconds=5))
    return value


@pytest.fixture
def scope():
    return TrustedRuntimeScope(
        tenant_id="tenant_test001",
        workspace_id="ws_test001",
        project_id="project_test001",
        run_id="run_test001",
        correlation_id="corr_test001",
        provider_allowlist=("openai",),
        approved_budget_inr_micros=100,
        approved_provider_cost_micros=100,
        allowed_data_regions=("global",),
    )


def payload(scope):
    return {
        "schemaVersion": 1,
        "tenantId": scope.tenant_id,
        "workspaceId": scope.workspace_id,
        "projectId": scope.project_id,
        "runId": scope.run_id,
        "correlationId": scope.correlation_id,
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "hello"}],
        "preferredProvider": "openai",
        "maxTokens": 64,
    }


def build_adapter(
    provider,
    scope,
    *,
    reader=None,
    writer=None,
    store=None,
    resolver=None,
    keymint=None,
):
    keymint = keymint or KeyMintClient(provider)
    return ZetakubeRuntimeAdapter(
        registry=Registry([provider]),
        artifact_reader=reader or AsyncMock(return_value=payload(scope)),
        artifact_writer=writer or AsyncMock(return_value="artifact_output001"),
        terminal_store=store or InMemoryTerminalResultStore(),
        cost_estimator=lambda provider_name, model, usage: 10,
        connection_resolver=resolver or ConnectionResolver(),
        keymint_client=keymint,
    )


@pytest.mark.asyncio
async def test_invokes_one_allowed_live_provider_and_normalizes_result(command, scope):
    provider = Provider()
    writer = AsyncMock(return_value="artifact_output001")
    adapter = build_adapter(provider, scope, writer=writer)

    result = await adapter.invoke(command, scope, Cancellation())

    assert result["eventType"] == "block.completed.v1"
    assert result["status"] == "succeeded"
    assert result["provider"] == "openai"
    assert result["model"] == "gpt-4o-mini"
    assert result["usage"]["inputTokens"] == 7
    assert result["usage"]["outputTokens"] == 3
    assert result["usage"]["requestCount"] == 1
    assert result["usage"]["estimatedInrMicros"] == 10
    assert result["routingDecision"] == {
        "reasonCode": "PREFERRED_PROVIDER_ALLOWED",
        "consideredProviders": ["openai"],
        "eligibleProviders": ["openai"],
        "selectedProvider": "openai",
        "dataRegion": "global",
    }
    assert provider.calls == 1
    writer.assert_awaited_once_with(
        {"schemaVersion": 1, "content": "safe answer", "finishReason": "stop"}, scope
    )


@pytest.mark.asyncio
async def test_zetakube_runtime_refuses_direct_credential_mode(command, scope):
    provider = Provider()
    adapter = build_adapter(provider, scope)
    adapter._registry.credential_mode = "direct"

    result = await adapter.invoke(command, scope, Cancellation())

    assert result["errorCode"] == "CAPABILITY_CONFIG_INVALID"
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_golden_routing_decisions_are_stable_and_explainable(command, scope):
    corpus = json.loads(ROUTING_GOLDEN.read_text())

    for case in corpus["cases"]:
        decisions = []
        for attempt in range(3):
            providers = [Provider(name=name) for name in case["availableProviders"]]
            selected = case["selectedProvider"]
            connection = ConnectionResolver(
                KeyMintConnection(
                    connection_ref="conn_provider001",
                    workspace_id=scope.workspace_id,
                    provider=selected,
                    data_region="global",
                    virtual_key_id="018f47d2-3ca2-7c63-a58f-55aa3a650001",
                    control_authorization="Bearer control-secret",
                    proxy_authorization="Bearer proxy-secret",
                )
            )
            task_scope = TrustedRuntimeScope(
                **{
                    **scope.__dict__,
                    "provider_allowlist": tuple(case["providerAllowlist"]),
                }
            )
            task_payload = payload(task_scope)
            task_payload["preferredProvider"] = case["preferredProvider"]
            task_command = copy.deepcopy(command)
            case_key = case["name"].replace(" ", "-")
            task_command["idempotencyKey"] = f"golden:{case_key}:{attempt}"
            adapter = ZetakubeRuntimeAdapter(
                registry=Registry(providers),
                artifact_reader=AsyncMock(return_value=task_payload),
                artifact_writer=AsyncMock(return_value="artifact_output001"),
                terminal_store=InMemoryTerminalResultStore(),
                cost_estimator=lambda provider_name, model, usage: 10,
                connection_resolver=connection,
                keymint_client=KeyMintClient(
                    next(provider for provider in providers if provider.name == selected)
                ),
            )

            result = await adapter.invoke(task_command, task_scope, Cancellation())
            assert result["status"] == "succeeded", case["name"]
            decisions.append(result["routingDecision"])

        assert decisions[0] == decisions[1] == decisions[2]
        assert decisions[0]["selectedProvider"] == case["selectedProvider"]
        assert decisions[0]["reasonCode"] == case["reasonCode"]


@pytest.mark.asyncio
async def test_data_region_constraint_overrides_provider_preference(command, scope):
    provider = Provider()
    disallowed_connection = KeyMintConnection(
        connection_ref="conn_provider001",
        workspace_id=scope.workspace_id,
        provider="openai",
        data_region="us",
        virtual_key_id="018f47d2-3ca2-7c63-a58f-55aa3a650001",
        control_authorization="Bearer control-secret",
        proxy_authorization="Bearer proxy-secret",
    )
    result = await build_adapter(
        provider,
        scope,
        resolver=ConnectionResolver(disallowed_connection),
    ).invoke(command, scope, Cancellation())

    assert result["errorCode"] == "POLICY_DENIED"
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_terminal_duplicate_does_not_invoke_provider_twice(command, scope):
    provider = Provider()
    store = InMemoryTerminalResultStore()
    adapter = build_adapter(provider, scope, store=store)

    first = await adapter.invoke(command, scope, Cancellation())
    second = await adapter.invoke(command, scope, Cancellation())

    assert second == first
    assert provider.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["workspace_id", "project_id", "run_id", "correlation_id"])
async def test_rejects_trusted_scope_mismatch_without_provider_call(command, scope, field):
    provider = Provider()
    values = {**scope.__dict__, field: "ws_attacker" if field == "workspace_id" else "run_attacker"}
    hostile_scope = TrustedRuntimeScope(**values)

    result = await build_adapter(provider, scope).invoke(command, hostile_scope, Cancellation())

    assert result["errorCode"] == "POLICY_DENIED"
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_rejects_payload_tenant_spoof_and_unapproved_provider(command, scope):
    provider = Provider()
    spoofed = payload(scope)
    spoofed["tenantId"] = "tenant_attacker"
    reader = AsyncMock(return_value=spoofed)
    result = await build_adapter(provider, scope, reader=reader).invoke(
        command, scope, Cancellation()
    )
    assert result["errorCode"] == "POLICY_DENIED"
    assert provider.calls == 0

    unapproved = payload(scope)
    unapproved["preferredProvider"] = "gemini"
    command["idempotencyKey"] += ":second"
    result = await build_adapter(
        provider, scope, reader=AsyncMock(return_value=unapproved)
    ).invoke(command, scope, Cancellation())
    assert result["errorCode"] == "POLICY_DENIED"
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_timeout_cancels_provider_and_returns_safe_error(command, scope):
    class SlowProvider(Provider):
        async def chat(self, request):
            self.calls += 1
            await asyncio.sleep(10)

    provider = SlowProvider()
    command["deadline"] = canonical_deadline(
        datetime.now(timezone.utc) + timedelta(milliseconds=20)
    )
    result = await build_adapter(provider, scope).invoke(command, scope, Cancellation())

    assert result["errorCode"] == "DEADLINE_EXCEEDED"
    assert result["retryable"] is False
    assert "detail" not in result
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_cancellation_is_acknowledged_without_output(command, scope):
    provider = Provider()
    cancellation = Cancellation()
    cancellation.cancel()

    result = await build_adapter(provider, scope).invoke(command, scope, cancellation)

    assert result["eventType"] == "block.completed.v1"
    assert result["status"] == "cancelled"
    assert result["cancellationAcknowledged"] is True
    assert result["outputArtifactRefs"] == []
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_inflight_cancellation_stops_the_selected_provider(command, scope):
    started = asyncio.Event()
    provider_cancelled = asyncio.Event()

    class SlowProvider(Provider):
        async def chat(self, request):
            self.calls += 1
            started.set()
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                provider_cancelled.set()
                raise

    provider = SlowProvider()
    cancellation = Cancellation()
    task = asyncio.create_task(
        build_adapter(provider, scope).invoke(command, scope, cancellation)
    )
    await started.wait()
    cancellation.cancel()
    result = await task

    assert result["status"] == "cancelled"
    assert result["cancellationAcknowledged"] is True
    assert provider_cancelled.is_set()
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_maps_provider_errors_without_leaking_native_body_or_simulating(command, scope):
    request = httpx.Request("POST", "https://provider.invalid/chat")
    response = httpx.Response(429, request=request, text="secret provider diagnostic")
    provider = Provider(error=httpx.HTTPStatusError("raw secret", request=request, response=response))

    result = await build_adapter(provider, scope).invoke(command, scope, Cancellation())

    assert result["errorCode"] == "PROVIDER_RATE_LIMITED"
    assert result["retryable"] is True
    assert "secret" not in json.dumps(result)
    assert "outputArtifactRefs" not in result
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_budget_and_operation_fail_closed(command, scope):
    provider = Provider()
    zero_budget = TrustedRuntimeScope(**{**scope.__dict__, "approved_budget_inr_micros": 0})
    result = await build_adapter(provider, zero_budget).invoke(command, zero_budget, Cancellation())
    assert result["errorCode"] == "BUDGET_EXCEEDED"

    command["idempotencyKey"] += ":operation"
    command["operation"] = "simulate"
    result = await build_adapter(provider, scope).invoke(command, scope, Cancellation())
    assert result["errorCode"] == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_health_reports_only_safe_provider_booleans(scope):
    adapter = build_adapter(Provider(), scope)
    assert await adapter.health() == {
        "status": "healthy",
        "runtime": "model.smart",
        "providers": {"openai": True},
    }


@pytest.mark.asyncio
async def test_worker_task_cancellation_propagates(command, scope):
    class SlowProvider(Provider):
        async def chat(self, request):
            self.calls += 1
            await asyncio.sleep(10)

    adapter = build_adapter(SlowProvider(), scope)
    task = asyncio.create_task(adapter.invoke(command, scope, Cancellation()))
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_artifact_failure_maps_to_safe_retryable_error(command, scope):
    reader = AsyncMock(side_effect=RuntimeError("bucket secret"))
    result = await build_adapter(Provider(), scope, reader=reader).invoke(
        command, scope, Cancellation()
    )

    assert result["errorCode"] == "ARTIFACT_UNAVAILABLE"
    assert result["retryable"] is True
    assert "secret" not in json.dumps(result)


@pytest.mark.asyncio
async def test_keymint_binding_uses_only_trusted_scope_and_connection(command, scope):
    provider = Provider()
    resolver = ConnectionResolver()
    keymint = KeyMintClient(provider)

    result = await build_adapter(
        provider, scope, resolver=resolver, keymint=keymint
    ).invoke(command, scope, Cancellation())

    assert result["status"] == "succeeded"
    assert resolver.calls == [("conn_provider001", "ws_test001")]
    connection, binding = keymint.bindings[0]
    assert connection.connection_ref == "conn_provider001"
    assert binding.workspace_id == scope.workspace_id
    assert binding.project_id == scope.project_id
    assert binding.zetakube_run_id == scope.run_id
    assert binding.model == "gpt-4o-mini"
    assert binding.operation == "chat.completions"
    assert binding.audience == "keymint-provider-proxy"
    assert binding.max_cost_micros == scope.approved_provider_cost_micros
    assert keymint.payloads[0][2]["messages"] == [{"role": "user", "content": "hello"}]
    assert keymint.revocations == [("conn_provider001", "cap_123")]


@pytest.mark.asyncio
async def test_connection_resolution_and_provider_binding_fail_closed(command, scope):
    provider = Provider()
    mismatched = KeyMintConnection(
        connection_ref="conn_provider001",
        workspace_id="ws_attacker",
        provider="openai",
        data_region="global",
        virtual_key_id="018f47d2-3ca2-7c63-a58f-55aa3a650001",
        control_authorization="Bearer control-secret",
        proxy_authorization="Bearer proxy-secret",
    )
    keymint = KeyMintClient(provider)

    result = await build_adapter(
        provider,
        scope,
        resolver=ConnectionResolver(connection=mismatched),
        keymint=keymint,
    ).invoke(command, scope, Cancellation())

    assert result["errorCode"] == "POLICY_DENIED"
    assert keymint.bindings == []
    assert provider.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "code", "retryable"),
    [
        (KeyMintRuntimeError("CAPABILITY_DENIED"), "CAPABILITY_DENIED", False),
        (KeyMintRuntimeError("CAPABILITY_EXPIRED"), "CAPABILITY_EXPIRED", False),
        (
            KeyMintRuntimeError("CAPABILITY_UNAVAILABLE", retryable=True),
            "CAPABILITY_UNAVAILABLE",
            True,
        ),
    ],
)
async def test_capability_issue_revocation_or_expiry_failure_is_safe(
    command, scope, error, code, retryable
):
    provider = Provider()
    keymint = KeyMintClient(provider, issue_error=error)

    result = await build_adapter(provider, scope, keymint=keymint).invoke(
        command, scope, Cancellation()
    )

    assert result["errorCode"] == code
    assert result["retryable"] is retryable
    assert "control-secret" not in json.dumps(result)
    assert "proxy-secret" not in json.dumps(result)
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_revocation_cleanup_failure_does_not_retry_completed_provider_call(command, scope):
    provider = Provider()
    keymint = KeyMintClient(
        provider,
        revoke_error=KeyMintRuntimeError("CAPABILITY_REVOKE_FAILED", retryable=True),
    )

    result = await build_adapter(provider, scope, keymint=keymint).invoke(
        command, scope, Cancellation()
    )

    assert result["status"] == "succeeded"
    assert provider.calls == 1
    assert keymint.revocations == [("conn_provider001", "cap_123")]


@pytest.mark.asyncio
async def test_missing_connection_or_provider_cost_authority_is_rejected(command, scope):
    provider = Provider()
    command["connectionRefs"] = []
    result = await build_adapter(provider, scope).invoke(command, scope, Cancellation())
    assert result["errorCode"] == "INVALID_INPUT"

    command["connectionRefs"] = ["conn_provider001"]
    command["idempotencyKey"] += ":cost"
    no_cost_authority = TrustedRuntimeScope(
        **{**scope.__dict__, "approved_provider_cost_micros": 0}
    )
    result = await build_adapter(provider, no_cost_authority).invoke(
        command, no_cost_authority, Cancellation()
    )
    assert result["errorCode"] == "POLICY_DENIED"
    assert provider.calls == 0
