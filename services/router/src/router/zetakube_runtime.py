"""Narrow Zetakube Runtime v1 adapter for KubeMind model routing.

This module is deliberately independent of the FastAPI gateway.  The caller
supplies trusted execution scope, artifact and idempotency boundaries, and the
existing provider registry.  KubeMind never reconstructs tenant identity from
the command body and never converts a live-provider failure into demo output.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from router.keymint_runtime import (
    CapabilityBinding,
    ConnectionResolver,
    KEYMINT_PROVIDER_PROXY_AUDIENCE,
    KeyMintRuntimeClient,
    KeyMintRuntimeError,
    openai_chat_payload,
)
from router.models import ChatRequest, Message


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*_[A-Za-z0-9][A-Za-z0-9._-]{0,126}$")
_NAME = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_ARTIFACT = re.compile(r"^artifact_[A-Za-z0-9][A-Za-z0-9._-]{0,126}$")
_CONNECTION = re.compile(r"^conn_[A-Za-z0-9][A-Za-z0-9._-]{0,126}$")
_IDEMPOTENCY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_UTC_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?Z$"
)
_SAFE_PROVIDER_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")


class CommandEnvelopeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    command_id: str = Field(alias="commandId", min_length=1, max_length=128)
    schema_version: int = Field(alias="schemaVersion")
    workspace_id: str = Field(alias="workspaceId", min_length=1, max_length=128)
    project_id: str = Field(alias="projectId", min_length=1, max_length=128)
    kube_version_id: str = Field(alias="kubeVersionId", min_length=1, max_length=128)
    run_id: str = Field(alias="runId", min_length=1, max_length=128)
    block_run_id: str = Field(alias="blockRunId", min_length=1, max_length=128)
    runtime: str = Field(min_length=1, max_length=128)
    operation: str = Field(min_length=1, max_length=128)
    input_artifact_refs: list[str] = Field(alias="inputArtifactRefs", max_length=64)
    connection_refs: list[str] = Field(alias="connectionRefs", max_length=64)
    policy_ref: str = Field(alias="policyRef", min_length=1, max_length=128)
    deadline: datetime
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=128)
    correlation_id: str = Field(alias="correlationId", min_length=1, max_length=128)

    @field_validator(
        "command_id",
        "workspace_id",
        "project_id",
        "kube_version_id",
        "run_id",
        "block_run_id",
        "policy_ref",
        "correlation_id",
    )
    @classmethod
    def identifiers_are_canonical(cls, value: str) -> str:
        if not _IDENTIFIER.fullmatch(value):
            raise ValueError("invalid canonical identifier")
        return value

    @field_validator("runtime", "operation")
    @classmethod
    def names_are_canonical(cls, value: str) -> str:
        if not _NAME.fullmatch(value):
            raise ValueError("invalid canonical name")
        return value

    @field_validator("input_artifact_refs")
    @classmethod
    def artifacts_are_canonical_and_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or not all(_ARTIFACT.fullmatch(v) for v in values):
            raise ValueError("invalid or duplicate artifact reference")
        return values

    @field_validator("connection_refs")
    @classmethod
    def connections_are_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or not all(_CONNECTION.fullmatch(v) for v in values):
            raise ValueError("invalid or duplicate connection reference")
        return values

    @field_validator("deadline", mode="before")
    @classmethod
    def deadline_is_canonical_utc(cls, value: Any) -> Any:
        if not isinstance(value, str) or not _UTC_TIMESTAMP.fullmatch(value):
            raise ValueError("deadline must be a canonical UTC timestamp")
        return value

    @field_validator("idempotency_key")
    @classmethod
    def idempotency_key_is_canonical(cls, value: str) -> str:
        if not _IDEMPOTENCY.fullmatch(value):
            raise ValueError("invalid idempotency key")
        return value

    @field_validator("schema_version")
    @classmethod
    def schema_is_v1(cls, value: int) -> int:
        if value != 1:
            raise ValueError("unsupported schema version")
        return value


class ModelRouteInputV1(BaseModel):
    """Payload read from the command's single input artifact."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schemaVersion")
    tenant_id: str = Field(alias="tenantId", min_length=1, max_length=128)
    workspace_id: str = Field(alias="workspaceId", min_length=1, max_length=128)
    project_id: str = Field(alias="projectId", min_length=1, max_length=128)
    run_id: str = Field(alias="runId", min_length=1, max_length=128)
    correlation_id: str = Field(alias="correlationId", min_length=1, max_length=128)
    model: str = Field(min_length=1, max_length=128)
    messages: list[Message] = Field(min_length=1, max_length=256)
    preferred_provider: Optional[str] = Field(default=None, alias="preferredProvider")
    policy: str = Field(default="cost", pattern="^(cost|quality|latency)$")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, alias="maxTokens", ge=1, le=1_000_000)
    top_p: float = Field(default=1.0, alias="topP", ge=0.0, le=1.0)

    @field_validator("schema_version")
    @classmethod
    def payload_schema_is_v1(cls, value: int) -> int:
        if value != 1:
            raise ValueError("unsupported payload schema version")
        return value

    @field_validator("model", "preferred_provider")
    @classmethod
    def route_names_are_safe(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not _NAME.fullmatch(value):
            raise ValueError("invalid routing name")
        return value


@dataclass(frozen=True)
class TrustedRuntimeScope:
    tenant_id: str
    workspace_id: str
    project_id: str
    run_id: str
    correlation_id: str
    provider_allowlist: tuple[str, ...]
    approved_budget_inr_micros: int
    approved_provider_cost_micros: int
    allowed_data_regions: tuple[str, ...]


class CancellationSignal(Protocol):
    def is_cancelled(self) -> bool: ...

    async def wait(self) -> None: ...


class TerminalResultStore(Protocol):
    async def get(self, tenant_id: str, idempotency_key: str) -> Optional[Dict[str, Any]]: ...

    async def claim(self, tenant_id: str, idempotency_key: str, command_id: str) -> bool: ...

    async def complete(
        self, tenant_id: str, idempotency_key: str, command_id: str, result: Dict[str, Any]
    ) -> None: ...

    async def release(self, tenant_id: str, idempotency_key: str, command_id: str) -> None: ...


ArtifactReader = Callable[[str, TrustedRuntimeScope], Awaitable[Mapping[str, Any]]]
ArtifactWriter = Callable[[Mapping[str, Any], TrustedRuntimeScope], Awaitable[str]]
CostEstimator = Callable[[str, str, Mapping[str, int]], int]


class RuntimeAdapterError(Exception):
    def __init__(self, code: str, *, retryable: bool = False):
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class RuntimeCancellation(Exception):
    """Explicit Zetakube cancellation, distinct from worker task cancellation."""


class ZetakubeRuntimeAdapter:
    RUNTIME = "model.smart"
    OPERATION = "generate"

    def __init__(
        self,
        *,
        registry: Any,
        artifact_reader: ArtifactReader,
        artifact_writer: ArtifactWriter,
        terminal_store: TerminalResultStore,
        cost_estimator: CostEstimator,
        connection_resolver: ConnectionResolver,
        keymint_client: KeyMintRuntimeClient,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._registry = registry
        self._artifact_reader = artifact_reader
        self._artifact_writer = artifact_writer
        self._terminal_store = terminal_store
        self._cost_estimator = cost_estimator
        self._connection_resolver = connection_resolver
        self._keymint_client = keymint_client
        self._now = now

    async def invoke(
        self,
        raw_command: Mapping[str, Any],
        scope: TrustedRuntimeScope,
        cancellation: CancellationSignal,
    ) -> Dict[str, Any]:
        command: Optional[CommandEnvelopeV1] = None
        claimed = False
        try:
            command = CommandEnvelopeV1.model_validate(raw_command)
            self._validate_scope(command, scope)
            self._validate_operation(command)

            cached = await self._terminal_store.get(scope.tenant_id, command.idempotency_key)
            if cached is not None:
                if cached.get("commandId") != command.command_id:
                    raise RuntimeAdapterError("INVALID_INPUT")
                return dict(cached)

            claimed = await self._terminal_store.claim(
                scope.tenant_id, command.idempotency_key, command.command_id
            )
            if not claimed:
                cached = await self._terminal_store.get(scope.tenant_id, command.idempotency_key)
                if cached is not None and cached.get("commandId") == command.command_id:
                    return dict(cached)
                raise RuntimeAdapterError("RUNTIME_UNAVAILABLE", retryable=True)

            result = await self._invoke_claimed(command, scope, cancellation)
            await self._terminal_store.complete(
                scope.tenant_id, command.idempotency_key, command.command_id, result
            )
            return result
        except (ValidationError, ValueError, TypeError):
            return self._error(command, raw_command, "INVALID_INPUT", False)
        except RuntimeAdapterError as exc:
            result = self._error(command, raw_command, exc.code, exc.retryable)
            if command is not None and claimed:
                await self._terminal_store.complete(
                    scope.tenant_id, command.idempotency_key, command.command_id, result
                )
            return result
        except KeyMintRuntimeError as exc:
            result = self._error(command, raw_command, exc.code, exc.retryable)
            if command is not None and claimed:
                await self._terminal_store.complete(
                    scope.tenant_id, command.idempotency_key, command.command_id, result
                )
            return result
        except RuntimeCancellation:
            if command is None:
                return self._error(command, raw_command, "CANCELLED", False)
            result = self._cancelled(command)
            if claimed:
                await self._terminal_store.complete(
                    scope.tenant_id, command.idempotency_key, command.command_id, result
                )
            return result
        except asyncio.CancelledError:
            if command is not None and claimed:
                await asyncio.shield(
                    self._terminal_store.release(
                        scope.tenant_id, command.idempotency_key, command.command_id
                    )
                )
            raise
        except Exception as exc:
            code, retryable = _safe_provider_error(exc)
            result = self._error(command, raw_command, code, retryable)
            if command is not None and claimed:
                await self._terminal_store.complete(
                    scope.tenant_id, command.idempotency_key, command.command_id, result
                )
            return result

    async def _invoke_claimed(
        self,
        command: CommandEnvelopeV1,
        scope: TrustedRuntimeScope,
        cancellation: CancellationSignal,
    ) -> Dict[str, Any]:
        if getattr(self._registry, "credential_mode", "keymint") != "keymint":
            raise RuntimeAdapterError("CAPABILITY_CONFIG_INVALID")
        if cancellation.is_cancelled():
            return self._cancelled(command)

        remaining = (command.deadline - self._now()).total_seconds()
        if remaining <= 0:
            raise RuntimeAdapterError("DEADLINE_EXCEEDED")
        if len(command.input_artifact_refs) != 1 or len(command.connection_refs) != 1:
            raise RuntimeAdapterError("INVALID_INPUT")
        if (
            not scope.provider_allowlist
            or not all(_NAME.fullmatch(name) for name in scope.provider_allowlist)
            or not scope.allowed_data_regions
            or not all(_NAME.fullmatch(name) for name in scope.allowed_data_regions)
            or scope.approved_budget_inr_micros < 0
            or scope.approved_provider_cost_micros <= 0
        ):
            raise RuntimeAdapterError("POLICY_DENIED")

        try:
            raw_payload = await self._artifact_reader(command.input_artifact_refs[0], scope)
        except Exception as exc:
            raise RuntimeAdapterError("ARTIFACT_UNAVAILABLE", retryable=True) from exc
        payload = ModelRouteInputV1.model_validate(raw_payload)
        self._validate_payload_scope(payload, scope)

        candidates = self._registry.eligible_providers(
            payload.model,
            pool=scope.provider_allowlist,
            policy=payload.policy,
            keymint_managed=True,
        )
        reason_code = "POLICY_ORDERED_SELECTION"
        if payload.preferred_provider:
            if payload.preferred_provider not in scope.provider_allowlist:
                raise RuntimeAdapterError("POLICY_DENIED")
            preferred = [p for p in candidates if p.name == payload.preferred_provider]
            if preferred:
                candidates = preferred + [
                    provider for provider in candidates if provider.name != payload.preferred_provider
                ]
                reason_code = "PREFERRED_PROVIDER_ALLOWED"
            else:
                reason_code = "PREFERRED_PROVIDER_UNAVAILABLE"
        if not candidates:
            raise RuntimeAdapterError("PROVIDER_UNAVAILABLE", retryable=True)

        # One selected live provider, one attempt. KMI-006 owns constrained
        # failover; this adapter must never manufacture simulation output.
        provider = candidates[0]
        try:
            connection = await self._connection_resolver.resolve(
                command.connection_refs[0], scope.workspace_id
            )
        except KeyMintRuntimeError:
            raise
        except Exception as exc:
            raise RuntimeAdapterError("CAPABILITY_UNAVAILABLE", retryable=True) from exc
        if (
            connection.connection_ref != command.connection_refs[0]
            or connection.workspace_id != scope.workspace_id
            or connection.provider != provider.name
            or connection.data_region not in scope.allowed_data_regions
        ):
            raise RuntimeAdapterError("POLICY_DENIED")

        request = ChatRequest(
            model=payload.model,
            messages=payload.messages,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            top_p=payload.top_p,
            stream=False,
            enable_cache=False,
            policy=payload.policy,
        )
        capability_deadline = min(
            command.deadline,
            self._now() + timedelta(minutes=15),
        )
        binding = CapabilityBinding(
            workspace_id=scope.workspace_id,
            project_id=scope.project_id,
            zetakube_run_id=scope.run_id,
            model=payload.model,
            operation="chat.completions",
            audience=KEYMINT_PROVIDER_PROXY_AUDIENCE,
            expires_at=capability_deadline,
            max_cost_micros=scope.approved_provider_cost_micros,
        )
        grant = await self._keymint_client.issue(connection, binding)
        started = time.perf_counter()
        try:
            response = await _await_provider(
                self._keymint_client.chat(connection, grant, openai_chat_payload(request)),
                cancellation,
                remaining,
            )
        finally:
            # One-use is the primary replay control. Revocation shortens the
            # exposure window when KeyMint rejected the proxy call before
            # redemption. A cleanup failure cannot make a completed provider
            # side effect retry, and is therefore intentionally non-terminal.
            try:
                await self._keymint_client.revoke(connection, grant.capability_id)
            except (KeyMintRuntimeError, Exception):
                pass
        elapsed_ms = max(0, round((time.perf_counter() - started) * 1000))

        usage = _normalize_usage(response.get("usage"), elapsed_ms)
        try:
            estimated_micros = self._cost_estimator(provider.name, payload.model, usage)
        except Exception as exc:
            raise RuntimeAdapterError("BUDGET_EXCEEDED") from exc
        if not isinstance(estimated_micros, int) or isinstance(estimated_micros, bool):
            raise RuntimeAdapterError("BUDGET_EXCEEDED")
        if estimated_micros < 0:
            raise RuntimeAdapterError("BUDGET_EXCEEDED")
        if estimated_micros > scope.approved_budget_inr_micros:
            raise RuntimeAdapterError("BUDGET_EXCEEDED")
        usage["estimatedInrMicros"] = estimated_micros

        try:
            output_ref = await self._artifact_writer(_safe_output(response), scope)
        except Exception as exc:
            raise RuntimeAdapterError("ARTIFACT_UNAVAILABLE", retryable=True) from exc
        if not _ARTIFACT.fullmatch(output_ref):
            raise RuntimeAdapterError("ARTIFACT_UNAVAILABLE", retryable=True)

        provider_request_id = response.get("id")
        result: Dict[str, Any] = {
            **self._base_event(command),
            "eventType": "block.completed.v1",
            "status": "succeeded",
            "outputArtifactRefs": [output_ref],
            "usage": usage,
            "provider": provider.name,
            "model": payload.model,
            "routingDecision": {
                "reasonCode": reason_code,
                "consideredProviders": sorted(set(scope.provider_allowlist)),
                "eligibleProviders": [candidate.name for candidate in candidates],
                "selectedProvider": provider.name,
                "dataRegion": connection.data_region,
            },
        }
        if isinstance(provider_request_id, str) and _SAFE_PROVIDER_REQUEST_ID.fullmatch(
            provider_request_id
        ):
            result["providerRequestId"] = provider_request_id
        return result

    async def health(self) -> Dict[str, Any]:
        try:
            raw_statuses = await self._registry.health_check_all()
        except Exception:
            return {"status": "unavailable", "runtime": self.RUNTIME}
        statuses = _normalize_health(raw_statuses)
        healthy = any(statuses.values())
        return {
            "status": "healthy" if healthy else "unavailable",
            "runtime": self.RUNTIME,
            "providers": statuses,
        }

    def _validate_scope(self, command: CommandEnvelopeV1, scope: TrustedRuntimeScope) -> None:
        if not scope.tenant_id or (
            command.workspace_id != scope.workspace_id
            or command.project_id != scope.project_id
            or command.run_id != scope.run_id
            or command.correlation_id != scope.correlation_id
        ):
            raise RuntimeAdapterError("POLICY_DENIED")

    def _validate_operation(self, command: CommandEnvelopeV1) -> None:
        if command.runtime != self.RUNTIME or command.operation != self.OPERATION:
            raise RuntimeAdapterError("INVALID_INPUT")

    @staticmethod
    def _validate_payload_scope(payload: ModelRouteInputV1, scope: TrustedRuntimeScope) -> None:
        if (
            payload.tenant_id != scope.tenant_id
            or payload.workspace_id != scope.workspace_id
            or payload.project_id != scope.project_id
            or payload.run_id != scope.run_id
            or payload.correlation_id != scope.correlation_id
        ):
            raise RuntimeAdapterError("POLICY_DENIED")

    @staticmethod
    def _base_event(command: CommandEnvelopeV1) -> Dict[str, Any]:
        event_seed = f"{command.command_id}:{command.block_run_id}"
        event_id = hashlib.sha256(event_seed.encode("utf-8")).hexdigest()[:24]
        return {
            "eventId": f"evt_{event_id}",
            "schemaVersion": 1,
            "commandId": command.command_id,
            "workspaceId": command.workspace_id,
            "projectId": command.project_id,
            "runId": command.run_id,
            "blockRunId": command.block_run_id,
            "correlationId": command.correlation_id,
        }

    def _cancelled(self, command: CommandEnvelopeV1) -> Dict[str, Any]:
        return {
            **self._base_event(command),
            "eventType": "block.completed.v1",
            "status": "cancelled",
            "outputArtifactRefs": [],
            "usage": {"requestCount": 0},
            "cancellationAcknowledged": True,
        }

    def _error(
        self,
        command: Optional[CommandEnvelopeV1],
        raw_command: Mapping[str, Any],
        code: str,
        retryable: bool,
    ) -> Dict[str, Any]:
        if command is not None:
            base = self._base_event(command)
        else:
            base = _safe_raw_event_scope(raw_command)
        return {
            **base,
            "eventType": "block.failed.v1",
            "status": "failed",
            "errorCode": code,
            "retryable": retryable,
        }


async def _await_provider(
    provider_call: Awaitable[Mapping[str, Any]],
    cancellation: CancellationSignal,
    timeout_seconds: float,
) -> Dict[str, Any]:
    call_task = asyncio.ensure_future(provider_call)
    cancel_task = asyncio.create_task(cancellation.wait())
    try:
        done, _ = await asyncio.wait(
            {call_task, cancel_task},
            timeout=timeout_seconds,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if cancel_task in done:
            call_task.cancel()
            await asyncio.gather(call_task, return_exceptions=True)
            raise RuntimeCancellation
        if call_task not in done:
            call_task.cancel()
            await asyncio.gather(call_task, return_exceptions=True)
            raise RuntimeAdapterError("DEADLINE_EXCEEDED")
        return dict(await call_task)
    finally:
        cancel_task.cancel()
        await asyncio.gather(cancel_task, return_exceptions=True)


def _normalize_usage(raw: Any, elapsed_ms: int) -> Dict[str, int]:
    usage = raw if isinstance(raw, Mapping) else {}

    def non_negative(*keys: str) -> int:
        for key in keys:
            value = usage.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                return value
        return 0

    input_tokens = non_negative("inputTokens", "input_tokens", "prompt_tokens", "promptTokenCount")
    output_tokens = non_negative(
        "outputTokens", "output_tokens", "completion_tokens", "candidatesTokenCount"
    )
    return {
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "requestCount": 1,
        "computeMilliseconds": max(0, elapsed_ms),
    }


def _safe_output(response: Mapping[str, Any]) -> Dict[str, Any]:
    choices = response.get("choices")
    content = ""
    finish_reason: Optional[str] = None
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        first = choices[0]
        message = first.get("message")
        if isinstance(message, Mapping) and isinstance(message.get("content"), str):
            content = message["content"]
        if isinstance(first.get("finish_reason"), str):
            finish_reason = first["finish_reason"][:64]
    output: Dict[str, Any] = {"schemaVersion": 1, "content": content}
    if finish_reason:
        output["finishReason"] = finish_reason
    return output


def _safe_provider_error(exc: Exception) -> tuple[str, bool]:
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return "PROVIDER_UNAVAILABLE", True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429:
            return "PROVIDER_RATE_LIMITED", True
        if 400 <= status < 500:
            return "PROVIDER_REJECTED", False
        return "PROVIDER_UNAVAILABLE", True
    if isinstance(exc, (httpx.ConnectError, ConnectionError)):
        return "PROVIDER_UNAVAILABLE", True
    return "INTERNAL_ERROR", False


def _normalize_health(raw: Any) -> Dict[str, bool]:
    if isinstance(raw, Mapping):
        return {str(name): bool(value) for name, value in raw.items()}
    if isinstance(raw, list):
        statuses: Dict[str, bool] = {}
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            name = item.get("name")
            healthy = item.get("healthy")
            if isinstance(name, str) and _NAME.fullmatch(name) and isinstance(healthy, bool):
                statuses[name] = healthy
        return statuses
    return {}


def _safe_raw_event_scope(raw: Mapping[str, Any]) -> Dict[str, Any]:
    def identifier(key: str, fallback: str) -> str:
        value = raw.get(key)
        return value if isinstance(value, str) and _IDENTIFIER.fullmatch(value) else fallback

    command_id = identifier("commandId", "cmd_invalid")
    block_run_id = identifier("blockRunId", "brun_invalid")
    digest = hashlib.sha256(f"{command_id}:{block_run_id}".encode("utf-8")).hexdigest()[:24]
    return {
        "eventId": f"evt_{digest}",
        "schemaVersion": 1,
        "commandId": command_id,
        "workspaceId": identifier("workspaceId", "ws_invalid"),
        "projectId": identifier("projectId", "project_invalid"),
        "runId": identifier("runId", "run_invalid"),
        "blockRunId": block_run_id,
        "correlationId": identifier("correlationId", "corr_invalid"),
    }


class InMemoryTerminalResultStore:
    """Test-only store; production callers must inject a durable implementation."""

    def __init__(self):
        self._terminal: Dict[tuple[str, str], Dict[str, Any]] = {}
        self._claims: Dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    async def get(self, tenant_id: str, idempotency_key: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            value = self._terminal.get((tenant_id, idempotency_key))
            return json.loads(json.dumps(value)) if value is not None else None

    async def claim(self, tenant_id: str, idempotency_key: str, command_id: str) -> bool:
        key = (tenant_id, idempotency_key)
        async with self._lock:
            if key in self._terminal or key in self._claims:
                return False
            self._claims[key] = command_id
            return True

    async def complete(
        self, tenant_id: str, idempotency_key: str, command_id: str, result: Dict[str, Any]
    ) -> None:
        key = (tenant_id, idempotency_key)
        async with self._lock:
            if self._claims.get(key) != command_id:
                raise RuntimeError("idempotency claim lost")
            self._terminal[key] = json.loads(json.dumps(result))
            self._claims.pop(key, None)

    async def release(self, tenant_id: str, idempotency_key: str, command_id: str) -> None:
        key = (tenant_id, idempotency_key)
        async with self._lock:
            if self._claims.get(key) == command_id:
                self._claims.pop(key, None)
