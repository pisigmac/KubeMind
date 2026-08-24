"""PII / secret redaction.

The implementation moved to ``kubemind_policy`` so the router can enforce the
same rules inline, before a prompt reaches a provider. This module re-exports
it to keep sentinel's imports stable.
"""

from kubemind_policy.redaction import (  # noqa: F401
    DEFAULT_MODES,
    PII_MODES,
    SECRET_MODES,
    detect,
    redact_attributes,
    redact_string,
)

__all__ = [
    "DEFAULT_MODES",
    "PII_MODES",
    "SECRET_MODES",
    "detect",
    "redact_attributes",
    "redact_string",
]
