"""Shared content-sensitivity detectors for KubeMind.

Owned jointly by router (inline enforcement, before dispatch) and sentinel
(post-hoc annotation, at span ingest). One implementation, one version, so a
rule change cannot make the two disagree about the same prompt.
"""

from kubemind_policy.redaction import (
    DEFAULT_MODES,
    PII_MODES,
    detect,
    redact_attributes,
    redact_string,
)
from kubemind_policy.guardrails import (
    annotate_attributes,
    extract_text_from_attributes,
    score_injection,
)

__all__ = [
    "DEFAULT_MODES",
    "PII_MODES",
    "detect",
    "redact_attributes",
    "redact_string",
    "annotate_attributes",
    "extract_text_from_attributes",
    "score_injection",
]
