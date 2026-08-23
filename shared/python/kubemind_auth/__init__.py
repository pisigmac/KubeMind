"""Workspace-bound API key authentication, shared by every KubeMind service.

`X-Workspace-ID` was previously trusted as-is. Any caller could read another
tenant's usage, spans and cache, and could attribute audit records to a
workspace they do not own -- which makes the audit trail worthless as evidence.
The workspace is now derived from the key.

Configuration, in precedence order:

* ``KUBEMIND_API_KEYS`` -- ``key:workspace`` pairs, comma separated
* ``auth.keys`` in a service config -- key (or ``${ENV_VAR}``) to workspace

When no keys are configured the services stay in open mode so local development
keeps working, but they say so loudly at startup. Set
``KUBEMIND_AUTH_REQUIRED=true`` to refuse to serve in that state.
``KUBEMIND_DEPLOYMENT=production`` always requires keys and refuses open mode.

One implementation on purpose: a gateway that enforces tenancy in front of
services that do not is a gateway you can walk around.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from kubemind_auth.deployment import deployment_profile, is_production

WORKSPACE_HEADER = "X-Workspace-ID"
API_KEY_HEADER = "X-API-Key"

__all__ = [
    "WORKSPACE_HEADER",
    "API_KEY_HEADER",
    "AuthResult",
    "AuthError",
    "Authenticator",
    "cors_origins",
    "deployment_profile",
    "is_production",
]


def cors_origins(default: Optional[List[str]] = None) -> List[str]:
    """Read allowed origins from KUBEMIND_CORS_ORIGINS.

    Every service previously shipped ``allow_origins=["*"]`` alongside
    ``allow_credentials=True``, which browsers reject and which is the wrong
    default regardless.
    """
    raw = os.environ.get("KUBEMIND_CORS_ORIGINS", "").strip()
    if not raw:
        return list(default or ["http://localhost:9000", "http://localhost:3000"])
    if raw == "*":
        raise ValueError("wildcard CORS is prohibited; configure explicit origins")
    return [o.strip() for o in raw.split(",") if o.strip()]


def valid_workspace(ws: str) -> bool:
    return bool(ws) and ws.replace("-", "").replace("_", "").isalnum()


@dataclass
class AuthResult:
    workspace_id: str
    authenticated: bool
    key_id: Optional[str] = None
    # A trusted in-cluster caller (router -> mind, router -> sentinel) acting
    # on behalf of an end user, so it may name any workspace.
    is_service: bool = False


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


class Authenticator:
    def __init__(
        self,
        keys: Optional[Dict[str, str]] = None,
        *,
        required: bool = False,
        default_workspace: str = "default",
        service_key: Optional[str] = None,
    ):
        self.keys = keys or {}
        self.required = required
        self.default_workspace = default_workspace
        # The router proxies mind and sentinel for every tenant, so it cannot
        # use a key bound to one workspace. This key says "I am another
        # KubeMind service, the workspace in the header is the real caller's".
        self.service_key = service_key or os.environ.get("KUBEMIND_SERVICE_KEY") or None

    @property
    def open_mode(self) -> bool:
        return not self.keys

    @classmethod
    def from_config(cls, config: Dict[str, Any] | None = None) -> "Authenticator":
        auth_cfg = ((config or {}).get("auth") or {})
        keys: Dict[str, str] = {}

        for raw_key, workspace in (auth_cfg.get("keys") or {}).items():
            key = str(raw_key)
            if key.startswith("${") and key.endswith("}"):
                key = os.environ.get(key[2:-1], "")
            if key and workspace:
                keys[key] = str(workspace)

        for pair in os.environ.get("KUBEMIND_API_KEYS", "").split(","):
            pair = pair.strip()
            if not pair or ":" not in pair:
                continue
            key, _, workspace = pair.partition(":")
            key, workspace = key.strip(), workspace.strip()
            if key and workspace:
                keys[key] = workspace

        required = os.environ.get(
            "KUBEMIND_AUTH_REQUIRED", str(auth_cfg.get("required", False))
        ).lower() in ("1", "true", "yes", "on")
        if is_production():
            required = True

        return cls(keys, required=required)

    def assert_production_safe(self, service: str = "kubemind") -> None:
        """Refuse to serve a production install in open mode."""
        if is_production() and self.open_mode:
            raise RuntimeError(
                f"[{service}] KUBEMIND_DEPLOYMENT=production refuses open-mode "
                "auth; configure KUBEMIND_API_KEYS"
            )

    def _lookup(self, presented: str) -> Optional[str]:
        # Compare against every configured key so a wrong key costs the same
        # time as a right one.
        match: Optional[str] = None
        for key, workspace in self.keys.items():
            if hmac.compare_digest(key, presented):
                match = workspace
        return match

    def authenticate(
        self, api_key: Optional[str], workspace_header: Optional[str]
    ) -> AuthResult:
        if api_key and self.service_key and hmac.compare_digest(self.service_key, api_key):
            ws = workspace_header or self.default_workspace
            if not valid_workspace(ws):
                raise AuthError("Invalid workspace identifier", status_code=400)
            return AuthResult(
                workspace_id=ws,
                authenticated=True,
                key_id="service",
                is_service=True,
            )

        if self.keys:
            if not api_key:
                raise AuthError("Missing API key")
            workspace = self._lookup(api_key)
            if not workspace:
                raise AuthError("Invalid API key")
            # A header may not redirect to a different workspace than the key's.
            if workspace_header and workspace_header != workspace:
                raise AuthError(
                    "Workspace header does not match API key", status_code=403
                )
            return AuthResult(workspace_id=workspace, authenticated=True, key_id=workspace)

        if self.required:
            raise AuthError(
                "Authentication required but no API keys are configured",
                status_code=503,
            )

        ws = workspace_header or self.default_workspace
        if not valid_workspace(ws):
            raise AuthError("Invalid workspace identifier", status_code=400)
        return AuthResult(workspace_id=ws, authenticated=False)

    def resolve_requested_workspace(
        self, auth: AuthResult, requested: Optional[str]
    ) -> str:
        """Validate a workspace supplied in a query string or request body.

        Sentinel takes `workspace_id` as a plain query parameter on several
        read endpoints, which is a cross-tenant read for anyone who guesses a
        name. Authenticated callers may only ever name their own workspace.
        """
        if not requested:
            return auth.workspace_id
        if auth.is_service:
            if not valid_workspace(requested):
                raise AuthError("Invalid workspace identifier", status_code=400)
            return requested
        if auth.authenticated and requested != auth.workspace_id:
            raise AuthError(
                "Cannot access a workspace other than the one bound to this key",
                status_code=403,
            )
        if not valid_workspace(requested):
            raise AuthError("Invalid workspace identifier", status_code=400)
        return requested

    def startup_banner(self, service: str = "kubemind") -> str:
        if self.keys:
            return f"[{service}] auth: {len(self.keys)} API key(s) bound to workspaces"
        return (
            f"[{service}] auth: OPEN MODE - {WORKSPACE_HEADER} is trusted without "
            "verification. Configure KUBEMIND_API_KEYS before exposing this "
            "service outside a trusted network."
        )
