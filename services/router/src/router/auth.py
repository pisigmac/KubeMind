"""Workspace-bound API key authentication.

`X-Workspace-ID` was previously trusted as-is, which meant any caller could
read another tenant's usage and cache and could attribute audit records to a
workspace they do not own. The workspace is now derived from the key.

Configuration, in precedence order:

* ``KUBEMIND_API_KEYS`` -- ``key:workspace`` pairs, comma separated
* ``auth.keys`` in gateway.yaml -- mapping of key (or ``${ENV_VAR}``) to workspace

When no keys are configured the router stays in open mode so local development
and existing deployments keep working, but it says so loudly at startup. Set
``KUBEMIND_AUTH_REQUIRED=true`` to refuse to serve in that state.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

WORKSPACE_HEADER = "X-Workspace-ID"
API_KEY_HEADER = "X-API-Key"


def _valid_workspace(ws: str) -> bool:
    return bool(ws) and ws.replace("-", "").replace("_", "").isalnum()


@dataclass
class AuthResult:
    workspace_id: str
    authenticated: bool
    key_id: Optional[str] = None


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
    ):
        self.keys = keys or {}
        self.required = required
        self.default_workspace = default_workspace

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

        return cls(keys, required=required)

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
        if self.keys:
            if not api_key:
                raise AuthError("Missing API key")
            workspace = self._lookup(api_key)
            if not workspace:
                raise AuthError("Invalid API key")
            # A header may narrow to a sub-workspace of the key's workspace but
            # may never redirect to a different one.
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
        if not _valid_workspace(ws):
            raise AuthError("Invalid workspace identifier", status_code=400)
        return AuthResult(workspace_id=ws, authenticated=False)

    def startup_banner(self) -> str:
        if self.keys:
            return f"[router] auth: {len(self.keys)} API key(s) bound to workspaces"
        return (
            "[router] auth: OPEN MODE - X-Workspace-ID is trusted without "
            "verification. Configure KUBEMIND_API_KEYS before exposing this "
            "router outside a trusted network."
        )
