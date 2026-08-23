"""Workspace-bound API key authentication.

The implementation moved to ``kubemind_auth`` so mind, agents and sentinel
enforce tenancy the same way. A gateway that enforces tenancy in front of
services that do not is a gateway you can walk around.

This module re-exports it to keep the router's imports stable.
"""

from kubemind_auth import (  # noqa: F401
    API_KEY_HEADER,
    WORKSPACE_HEADER,
    AuthError,
    Authenticator,
    AuthResult,
    cors_origins,
    deployment_profile,
    is_production,
    valid_workspace,
)

__all__ = [
    "API_KEY_HEADER",
    "WORKSPACE_HEADER",
    "AuthError",
    "Authenticator",
    "AuthResult",
    "cors_origins",
    "deployment_profile",
    "is_production",
    "valid_workspace",
]
