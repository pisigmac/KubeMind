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
from kubemind_policy.streaming import StreamingDeAnonymizer
from kubemind_policy.dlp import CustomDLPEngine, get_default_dlp
from kubemind_policy.wasm_hooks import WasmHookRunner, get_default_hook_runner
from kubemind_policy.multimodal import MultimodalPrivacyEngine, get_default_multimodal
from kubemind_policy.audio import AudioPrivacyEngine, get_default_audio_privacy
from kubemind_policy.network_guard import NetworkEgressGuard, get_default_network_guard

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
    "StreamingDeAnonymizer",
    "CustomDLPEngine",
    "get_default_dlp",
    "WasmHookRunner",
    "get_default_hook_runner",
    "MultimodalPrivacyEngine",
    "get_default_multimodal",
    "AudioPrivacyEngine",
    "get_default_audio_privacy",
    "NetworkEgressGuard",
    "get_default_network_guard",
]
