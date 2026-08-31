"""Centralized configuration & dynamic environment loader for KubeMind.

All service URLs, database connection strings, auth endpoints, and runtime flags
are resolved dynamically through this module rather than relying on hardcoded
static strings or scattered fallback URLs across individual modules.
"""

from __future__ import annotations

import os
from typing import List, Optional


def get_router_url(default: Optional[str] = None) -> str:
    """Return the resolved Router Gateway URL."""
    return os.environ.get(
        "ROUTER_URL",
        os.environ.get("KUBEMIND_ROUTER_URL", default or "http://localhost:9080"),
    ).rstrip("/")


def get_mind_url(default: Optional[str] = None) -> str:
    """Return the resolved Mind Context Engine URL."""
    return os.environ.get(
        "MIND_URL",
        os.environ.get("KUBEMIND_MIND_URL", default or "http://localhost:9081"),
    ).rstrip("/")


def get_agents_url(default: Optional[str] = None) -> str:
    """Return the resolved Agents Swarm Planner URL."""
    return os.environ.get(
        "AGENTS_URL",
        os.environ.get("KUBEMIND_AGENTS_URL", default or "http://localhost:9082"),
    ).rstrip("/")


def get_sentinel_url(default: Optional[str] = None) -> str:
    """Return the resolved Sentinel Ledger & Tracer URL."""
    return os.environ.get(
        "SENTINEL_URL",
        os.environ.get(
            "TRACER_URL",
            os.environ.get("KUBEMIND_SENTINEL_URL", default or "http://localhost:9083"),
        ),
    ).rstrip("/")


def get_dashboard_url(default: Optional[str] = None) -> str:
    """Return the resolved Operator Dashboard URL."""
    return os.environ.get(
        "DASHBOARD_URL",
        os.environ.get("KUBEMIND_DASHBOARD_URL", default or "http://localhost:9000"),
    ).rstrip("/")


def is_production() -> bool:
    """Return whether KubeMind is running in production mode."""
    return os.environ.get("KUBEMIND_DEPLOYMENT", "local").strip().lower() == "production"


def get_database_url(default: Optional[str] = None) -> str:
    """Return the PostgreSQL connection string.
    In production mode, strictly refuses default or plaintext insecure credentials.
    """
    raw = os.environ.get("DATABASE_URL")
    if not raw and (os.environ.get("POSTGRES_USER") and os.environ.get("POSTGRES_PASSWORD")):
        user = os.environ["POSTGRES_USER"]
        pw = os.environ["POSTGRES_PASSWORD"]
        host = os.environ.get("POSTGRES_HOST", "postgres")
        port = os.environ.get("POSTGRES_PORT", "5432")
        db = os.environ.get("POSTGRES_DB", "kubemind")
        raw = f"postgresql://{user}:{pw}@{host}:{port}/{db}"

    if is_production():
        if not raw or "kubemind:kubemind@" in raw or "postgres:postgres@" in raw:
            raise RuntimeError(
                "[Security Alert] KUBEMIND_DEPLOYMENT=production refuses default/insecure database credentials. "
                "Configure a secure DATABASE_URL or POSTGRES_PASSWORD in environment."
            )
        return raw

    if raw:
        return raw
    user = os.environ.get("POSTGRES_USER", "kubemind")
    pw = os.environ.get("POSTGRES_PASSWORD", "kubemind")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "kubemind")
    return default or f"postgresql://{user}:{pw}@{host}:{port}/{db}"


def get_redis_url(default: Optional[str] = None) -> str:
    """Return the Redis connection string."""
    return os.environ.get("REDIS_URL", default or "redis://localhost:6379/0")


def get_ollama_base_url(default: Optional[str] = None) -> str:
    """Return the local Ollama inference API endpoint."""
    return os.environ.get(
        "OLLAMA_BASE_URL",
        default or "http://localhost:11434",
    ).rstrip("/")


def get_auth_jwks_url(default: Optional[str] = None) -> str:
    """Return the OpenDesk / PiSigma Auth JWKS endpoint for RS256 token validation."""
    auth_service_url = os.environ.get("AUTH_SERVICE_URL", "http://localhost:8090").rstrip("/")
    return os.environ.get(
        "AUTH_JWKS_URL",
        f"{auth_service_url}/.well-known/jwks.json" if not default else default,
    )


def get_paydeck_url(default: Optional[str] = None) -> str:
    """Return the PayDeck Razorpay billing microservice URL."""
    return os.environ.get(
        "PAYDECK_URL",
        os.environ.get("PAYDECK_SERVICE_URL", default or "http://localhost:8787"),
    ).rstrip("/")


def get_cors_origins(default: Optional[List[str]] = None) -> List[str]:
    """Return CORS allowed origins parsed from environment or configuration."""
    raw = os.environ.get("KUBEMIND_CORS_ORIGINS", "").strip()
    if not raw:
        return list(default or ["http://localhost:9000", "http://localhost:3000"])
    if raw == "*":
        raise ValueError("wildcard CORS is prohibited; configure explicit origins")
    return [o.strip() for o in raw.split(",") if o.strip()]


__all__ = [
    "get_router_url",
    "get_mind_url",
    "get_agents_url",
    "get_sentinel_url",
    "get_dashboard_url",
    "get_database_url",
    "get_redis_url",
    "get_ollama_base_url",
    "get_auth_jwks_url",
    "get_paydeck_url",
    "get_cors_origins",
]
