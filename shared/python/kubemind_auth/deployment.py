"""Deployment profile: local laptop vs production sellable install."""

from __future__ import annotations

import os

LOCAL = "local"
PRODUCTION = "production"
_ENV = "KUBEMIND_DEPLOYMENT"


def deployment_profile() -> str:
    """Return ``local`` or ``production``.

    Unset and developer aliases (``dev``, ``development``) are local.
    Unknown values fail closed so a typo cannot silently open a cluster.
    """
    raw = os.environ.get(_ENV, LOCAL).strip().lower()
    if raw in {"", LOCAL, "dev", "development"}:
        return LOCAL
    if raw in {PRODUCTION, "prod"}:
        return PRODUCTION
    raise ValueError(f"{_ENV} must be local or production")


def is_production() -> bool:
    return deployment_profile() == PRODUCTION
