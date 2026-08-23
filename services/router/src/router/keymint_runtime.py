"""Fail-closed KeyMint boundary for the Zetakube runtime path.

Provider credentials remain inside KeyMint.  KubeMind receives an opaque
Connection resolution containing KeyMint control/proxy credentials, issues a
single-use capability, and forwards only that capability to KeyMint's proxy.
Neither request content nor credentials are included in raised errors.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping, Optional, Protocol
from urllib.parse import quote, urlparse

import httpx


KEYMINT_PROVIDER_PROXY_AUDIENCE = "keymint-provider-proxy"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")


class KeyMintRuntimeError(Exception):
    """Secret-safe integration failure understood by the runtime adapter."""

    def __init__(self, code: str, *, retryable: bool = False):
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class KeyMintConfig:
    base_url: str
    audience: str
    issue_timeout_seconds: float
    proxy_timeout_seconds: float
    revoke_timeout_seconds: float

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        environ: Optional[Mapping[str, str]] = None,
    ) -> "KeyMintConfig":
        env = environ if environ is not None else os.environ

        def value(name: str) -> Any:
            candidate = raw.get(name)
            if isinstance(candidate, str) and candidate.startswith("${") and candidate.endswith("}"):
                candidate = env.get(candidate[2:-1], "")
            return candidate

        base_url = str(value("base_url") or "").rstrip("/")
        audience = str(value("audience") or "")
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise KeyMintRuntimeError("CAPABILITY_CONFIG_INVALID")
        if audience != KEYMINT_PROVIDER_PROXY_AUDIENCE:
            raise KeyMintRuntimeError("CAPABILITY_CONFIG_INVALID")

        def timeout(name: str) -> float:
            try:
                result = float(value(name))
            except (TypeError, ValueError) as exc:
                raise KeyMintRuntimeError("CAPABILITY_CONFIG_INVALID") from exc
            if result <= 0 or result > 120:
                raise KeyMintRuntimeError("CAPABILITY_CONFIG_INVALID")
            return result

        return cls(
            base_url=base_url,
            audience=audience,
            issue_timeout_seconds=timeout("issue_timeout_seconds"),
            proxy_timeout_seconds=timeout("proxy_timeout_seconds"),
            revoke_timeout_seconds=timeout("revoke_timeout_seconds"),
        )


@dataclass(frozen=True)
class KeyMintConnection:
    """Trusted resolution of one Zetakube Connection reference.

    The virtual-key ID is the KeyMint policy/grant handle. KeyMint derives the
    exact provider-key ID from it. Tokens are excluded from repr so an
    accidental structured log of this object does not expose credentials.
    """

    connection_ref: str
    workspace_id: str
    provider: str
    data_region: str
    virtual_key_id: str
    control_authorization: str = field(repr=False)
    proxy_authorization: str = field(repr=False)


@dataclass(frozen=True)
class CapabilityBinding:
    workspace_id: str
    project_id: str
    zetakube_run_id: str
    model: str
    operation: str
    audience: str
    expires_at: datetime
    max_cost_micros: int


@dataclass(frozen=True)
class CapabilityGrant:
    capability_id: str
    token: str = field(repr=False)
    keymint_run_id: str
    expires_at: datetime


class ConnectionResolver(Protocol):
    async def resolve(self, connection_ref: str, workspace_id: str) -> KeyMintConnection: ...


class KeyMintRuntimeClient(Protocol):
    async def issue(
        self, connection: KeyMintConnection, binding: CapabilityBinding
    ) -> CapabilityGrant: ...

    async def chat(
        self,
        connection: KeyMintConnection,
        grant: CapabilityGrant,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...

    async def revoke(self, connection: KeyMintConnection, capability_id: str) -> None: ...


class HttpKeyMintRuntimeClient:
    """HTTP implementation with an injectable transport and no ambient secrets."""

    def __init__(self, config: KeyMintConfig, *, transport: Optional[httpx.AsyncBaseTransport] = None):
        self._config = config
        self._client = httpx.AsyncClient(base_url=config.base_url, transport=transport)

    async def issue(
        self, connection: KeyMintConnection, binding: CapabilityBinding
    ) -> CapabilityGrant:
        self._validate_connection(connection, binding)
        body = {
            "operations": [binding.operation],
            "models": [binding.model],
            "expires_at": binding.expires_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "max_uses": 1,
            "max_cost_micros": binding.max_cost_micros,
        }
        response = await self._request(
            "POST",
            f"/v1/virtual-keys/{quote(connection.virtual_key_id, safe='')}/capabilities",
            authorization=connection.control_authorization,
            json=body,
            timeout=self._config.issue_timeout_seconds,
        )
        if response.status_code != 201:
            raise _status_error(response.status_code)
        try:
            raw = response.json()
            expires_at = datetime.fromisoformat(str(raw["expires_at"]).replace("Z", "+00:00"))
            grant = CapabilityGrant(
                capability_id=str(raw["id"]),
                token=str(raw["token"]),
                keymint_run_id=str(raw["run_id"]),
                expires_at=expires_at,
            )
            if (
                raw.get("operations") != [binding.operation]
                or raw.get("models") != [binding.model]
                or raw.get("max_uses") != 1
                or int(raw.get("max_cost_micros", -1)) > binding.max_cost_micros
                or not grant.token.startswith("kmcap_")
                or not _SAFE_ID.fullmatch(grant.capability_id)
                or not _SAFE_ID.fullmatch(grant.keymint_run_id)
                or grant.expires_at.tzinfo is None
                or grant.expires_at > binding.expires_at
                or grant.expires_at <= datetime.now(timezone.utc)
            ):
                raise ValueError("invalid grant")
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise KeyMintRuntimeError("CAPABILITY_DENIED") from exc
        return grant

    async def chat(
        self,
        connection: KeyMintConnection,
        grant: CapabilityGrant,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        if grant.expires_at <= datetime.now(timezone.utc):
            raise KeyMintRuntimeError("CAPABILITY_EXPIRED")
        response = await self._request(
            "POST",
            "/v1/proxy/chat/completions",
            authorization=connection.proxy_authorization,
            headers={
                "X-KeyMint-Capability": grant.token,
                "X-KeyMint-Run-ID": grant.keymint_run_id,
            },
            json=dict(payload),
            timeout=self._config.proxy_timeout_seconds,
        )
        if response.status_code != 200:
            raise _status_error(response.status_code)
        try:
            result = response.json()
        except ValueError as exc:
            raise KeyMintRuntimeError("PROVIDER_UNAVAILABLE", retryable=True) from exc
        if not isinstance(result, Mapping):
            raise KeyMintRuntimeError("PROVIDER_UNAVAILABLE", retryable=True)
        return result

    async def revoke(self, connection: KeyMintConnection, capability_id: str) -> None:
        if not _SAFE_ID.fullmatch(capability_id):
            raise KeyMintRuntimeError("CAPABILITY_REVOKE_FAILED")
        response = await self._request(
            "PATCH",
            f"/v1/capabilities/{quote(capability_id, safe='')}/revoke",
            authorization=connection.control_authorization,
            timeout=self._config.revoke_timeout_seconds,
        )
        if response.status_code != 200:
            raise KeyMintRuntimeError(
                "CAPABILITY_REVOKE_FAILED", retryable=response.status_code >= 500
            )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        authorization: str,
        timeout: float,
        headers: Optional[Mapping[str, str]] = None,
        json: Optional[Mapping[str, Any]] = None,
    ) -> httpx.Response:
        if not authorization.startswith("Bearer ") or len(authorization) <= len("Bearer "):
            raise KeyMintRuntimeError("CAPABILITY_CONFIG_INVALID")
        safe_headers: MutableMapping[str, str] = {
            "Authorization": authorization,
            "Accept": "application/json",
        }
        if headers:
            safe_headers.update(headers)
        try:
            return await self._client.request(
                method, path, headers=safe_headers, json=json, timeout=timeout
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise KeyMintRuntimeError("CAPABILITY_UNAVAILABLE", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise KeyMintRuntimeError("CAPABILITY_UNAVAILABLE", retryable=True) from exc

    @staticmethod
    def _validate_connection(
        connection: KeyMintConnection, binding: CapabilityBinding
    ) -> None:
        if (
            connection.workspace_id != binding.workspace_id
            or not _SAFE_ID.fullmatch(connection.virtual_key_id)
            or not _SAFE_ID.fullmatch(connection.provider)
            or not _SAFE_ID.fullmatch(connection.data_region)
            or binding.audience != KEYMINT_PROVIDER_PROXY_AUDIENCE
            or binding.max_cost_micros <= 0
            or binding.expires_at.tzinfo is None
        ):
            raise KeyMintRuntimeError("CAPABILITY_DENIED")

    async def close(self) -> None:
        await self._client.aclose()


def _status_error(status_code: int) -> KeyMintRuntimeError:
    if status_code in (401, 403):
        return KeyMintRuntimeError("CAPABILITY_DENIED")
    if status_code == 408:
        return KeyMintRuntimeError("CAPABILITY_EXPIRED")
    if status_code == 429:
        return KeyMintRuntimeError("PROVIDER_RATE_LIMITED", retryable=True)
    if status_code == 402:
        return KeyMintRuntimeError("BUDGET_EXCEEDED")
    return KeyMintRuntimeError("CAPABILITY_UNAVAILABLE", retryable=status_code >= 500)


def openai_chat_payload(request: Any) -> Mapping[str, Any]:
    """Serialize only the supported non-streaming OpenAI-compatible surface."""

    result: dict[str, Any] = {
        "model": request.model,
        "messages": [{"role": item.role, "content": item.content} for item in request.messages],
        "temperature": request.temperature,
        "top_p": request.top_p,
        "stream": False,
    }
    if request.max_tokens is not None:
        result["max_tokens"] = request.max_tokens
    return result
