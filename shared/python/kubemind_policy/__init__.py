"""Shared content-sensitivity detectors for KubeMind.

Owned jointly by router (inline enforcement, before dispatch) and sentinel
(post-hoc annotation, at span ingest). One implementation, one version, so a
rule change cannot make the two disagree about the same prompt.
"""

from kubemind_policy.redaction import (
    DEFAULT_MODES,
    NER_MODES,
    PII_MODES,
    SECRET_MODES,
    detect,
    pseudonymize_string,
    redact_attributes,
    redact_string,
    restore_string,
)
from kubemind_policy.guardrails import (
    annotate_attributes,
    extract_text_from_attributes,
    score_injection,
)
from kubemind_policy.ner import (
    LocalNEREngine,
    NamedEntity,
    get_default_ner,
)

__all__ = [
    "DEFAULT_MODES",
    "NER_MODES",
    "PII_MODES",
    "SECRET_MODES",
    "detect",
    "pseudonymize_string",
    "redact_attributes",
    "redact_string",
    "restore_string",
    "annotate_attributes",
    "extract_text_from_attributes",
    "score_injection",
    "LocalNEREngine",
    "NamedEntity",
    "get_default_ner",
]
