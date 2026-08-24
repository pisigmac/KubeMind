"""Workspace-bound API key authentication and RBAC, shared by every KubeMind service.

Configuration, in precedence order:
* ``KUBEMIND_API_KEYS`` -- ``key:workspace`` or ``key:workspace:role`` tuples, comma separated
* ``auth.keys`` in a service config -- key to workspace (or object with workspace and role)

Roles:
* ``admin``: Full access to all endpoints, configurations, and audit verification (*).
* ``developer``: Can dispatch chat/completions, route, classify, query/ingest mind, read audit/usage.
* ``auditor``: Read-only access to audit logs, cryptographic ledger verification, and compliance statistics.
* ``viewer``: Read-only access to dashboard statistics, metrics, and usage.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from kubemind_auth.deployment import deployment_profile, is_production

WORKSPACE_HEADER = "X-Workspace-ID"
API_KEY_HEADER = "X-API-Key"


class Role(str, Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    AUDITOR = "auditor"
    VIEWER = "viewer"


ROLE_SCOPES: Dict[str, Set[str]] = {
    Role.ADMIN.value: {"*", "usage:org"},
    Role.DEVELOPER.value: {
        "chat",
        "route",
        "classify",
        "mind:query",
        "mind:ingest",
        "audit:read",
        "audit:write",
        "usage:read",
    },
    Role.AUDITOR.value: {
        "audit:read",
        "audit:verify",
        "usage:read",
    },
    Role.VIEWER.value: {
        "metrics:read",
        "dashboard:read",
        "usage:read",
    },
}


@dataclass
class KeyBinding:
    workspace: str
    role: str = Role.ADMIN.value

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            return self.workspace == other
        if isinstance(other, KeyBinding):
            return self.workspace == other.workspace and self.role == other.role
        return False

    def __str__(self) -> str:
        return self.workspace

    def __repr__(self) -> str:
        return f"KeyBinding(workspace={self.workspace!r}, role={self.role!r})"


def cors_origins(default: Optional[List[str]] = None) -> List[str]:
    """Read allowed origins from KUBEMIND_CORS_ORIGINS."""
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
    role: str = Role.ADMIN.value
    scopes: Set[str] = field(default_factory=lambda: {"*"})
    is_service: bool = False

    def has_scope(self, scope: str) -> bool:
        """Check if this auth context has the required permission scope."""
        if "*" in self.scopes or self.role == Role.ADMIN.value or self.is_service:
            return True
        return scope in self.scopes

    def assert_scope(self, scope: str) -> None:
        """Raise AuthError(403) if the required scope is missing."""
        if not self.has_scope(scope):
            raise AuthError(
                f"Forbidden: role '{self.role}' lacks required permission scope '{scope}'",
                status_code=403,
            )


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


class Authenticator:
    def __init__(
        self,
        keys: Optional[Dict[str, KeyBinding | str]] = None,
        *,
        required: bool = False,
        default_workspace: str = "default",
        service_key: Optional[str] = None,
    ):
        normalized_keys: Dict[str, KeyBinding] = {}
        for k, v in (keys or {}).items():
            if isinstance(v, KeyBinding):
                normalized_keys[k] = v
            elif isinstance(v, dict):
                normalized_keys[k] = KeyBinding(
                    workspace=str(v.get("workspace", default_workspace)),
                    role=str(v.get("role", Role.ADMIN.value)),
                )
            else:
                normalized_keys[k] = KeyBinding(workspace=str(v), role=Role.ADMIN.value)

        self.keys = normalized_keys
        self.required = required
        self.default_workspace = default_workspace
        self.service_key = service_key or os.environ.get("KUBEMIND_SERVICE_KEY") or None

    @property
    def open_mode(self) -> bool:
        return not self.keys

    @classmethod
    def from_config(cls, config: Dict[str, Any] | None = None) -> "Authenticator":
        auth_cfg = (config or {}).get("auth") or {}
        keys: Dict[str, KeyBinding] = {}

        for raw_key, spec in (auth_cfg.get("keys") or {}).items():
            key = str(raw_key)
            if key.startswith("${") and key.endswith("}"):
                key = os.environ.get(key[2:-1], "")
            if not key:
                continue
            if isinstance(spec, dict):
                ws = str(spec.get("workspace", "default"))
                role = str(spec.get("role", Role.ADMIN.value))
                keys[key] = KeyBinding(workspace=ws, role=role)
            elif spec:
                keys[key] = KeyBinding(workspace=str(spec), role=Role.ADMIN.value)

        for token in os.environ.get("KUBEMIND_API_KEYS", "").split(","):
            token = token.strip()
            if not token or ":" not in token:
                continue
            parts = [p.strip() for p in token.split(":")]
            if len(parts) == 2:
                key, workspace = parts
                role = Role.ADMIN.value
            elif len(parts) >= 3:
                key, workspace, role = parts[0], parts[1], parts[2]
            else:
                continue

            if key and workspace:
                keys[key] = KeyBinding(workspace=workspace, role=role)

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

    def _lookup(self, presented: str) -> Optional[KeyBinding]:
        match: Optional[KeyBinding] = None
        for key, binding in self.keys.items():
            if hmac.compare_digest(key, presented):
                match = binding
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
                role=Role.ADMIN.value,
                scopes={"*"},
                is_service=True,
            )

        if self.keys:
            if not api_key:
                raise AuthError("Missing API key")
            binding = self._lookup(api_key)
            if not binding:
                raise AuthError("Invalid API key")
            workspace = binding.workspace
            role = binding.role
            # A header may not redirect to a different workspace than the key's.
            if workspace_header and workspace_header != workspace:
                raise AuthError(
                    "Workspace header does not match API key", status_code=403
                )
            scopes = ROLE_SCOPES.get(role, {"*"} if role == Role.ADMIN.value else set())
            return AuthResult(
                workspace_id=workspace,
                authenticated=True,
                key_id=workspace,
                role=role,
                scopes=scopes,
            )

        if self.required:
            raise AuthError(
                "Authentication required but no API keys are configured",
                status_code=503,
            )

        ws = workspace_header or self.default_workspace
        if not valid_workspace(ws):
            raise AuthError("Invalid workspace identifier", status_code=400)
        return AuthResult(
            workspace_id=ws,
            authenticated=False,
            role=Role.ADMIN.value,
            scopes={"*"},
        )

    def resolve_requested_workspace(
        self, auth: AuthResult, requested: Optional[str]
    ) -> str:
        """Validate a workspace supplied in a query string or request body."""
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


__all__ = [
    "WORKSPACE_HEADER",
    "API_KEY_HEADER",
    "Role",
    "ROLE_SCOPES",
    "KeyBinding",
    "AuthResult",
    "AuthError",
    "Authenticator",
    "cors_origins",
    "deployment_profile",
    "is_production",
]
