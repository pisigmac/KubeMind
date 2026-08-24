"""PII / secret detection and redaction."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Tuple

from kubemind_policy.ner import get_default_ner

# mode -> (regex, replacement)
_PATTERNS: Dict[str, Tuple[re.Pattern, str]] = {
    "email": (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[REDACTED_EMAIL]",
    ),
    "phone": (
        re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "[REDACTED_PHONE]",
    ),
    "aws_key": (
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        "[REDACTED_AWS_KEY]",
    ),
    "bearer": (
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*"),
        "Bearer [REDACTED_TOKEN]",
    ),
    "private_key": (
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    "api_key": (
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*['\"]?[A-Za-z0-9\-._]{16,}['\"]?"
        ),
        "[REDACTED_API_KEY]",
    ),
}

# Personal data, as opposed to credentials. Policies usually treat these
# differently: an email or person is redactable, a private key is not.
NER_MODES = ("person", "address", "organization")
PII_MODES = ("email", "phone", "person", "address")
SECRET_MODES = ("aws_key", "bearer", "private_key", "api_key")

DEFAULT_MODES = list(_PATTERNS.keys()) + list(NER_MODES)


def _enabled() -> bool:
    return os.environ.get("KUBEMIND_REDACTION_ENABLED", "true").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _active_modes() -> List[str]:
    raw = os.environ.get("KUBEMIND_REDACTION_MODES", "")
    if raw.strip():
        return [m.strip() for m in raw.split(",") if m.strip() in DEFAULT_MODES]
    return DEFAULT_MODES


def detect(text: str, modes: List[str] | None = None) -> List[str]:
    """Return the detector names that fire on ``text`` without rewriting it.

    The router needs to know what is present before deciding what to do about
    it; redacting first would destroy the evidence the policy runs on.
    """
    if not text:
        return []
    modes = modes if modes is not None else _active_modes()
    hits = [mode for mode in modes if mode in _PATTERNS and _PATTERNS[mode][0].search(text)]
    
    ner_modes = [m for m in modes if m in NER_MODES]
    if ner_modes:
        ner_engine = get_default_ner()
        ner_entities = ner_engine.detect_entities(text, labels=ner_modes)
        for ent in ner_entities:
            if ent.label not in hits:
                hits.append(ent.label)
                
    return hits


def redact_string(value: str, modes: List[str] | None = None) -> Tuple[str, List[str]]:
    """Return (redacted_text, list of mode names that fired)."""
    modes = modes if modes is not None else _active_modes()
    found: List[str] = []
    out = value
    for mode in modes:
        if mode not in _PATTERNS:
            continue
        pat, repl = _PATTERNS[mode]
        new_out, n = pat.subn(repl, out)
        if n:
            found.append(mode)
            out = new_out
            
    ner_modes = [m for m in modes if m in NER_MODES]
    if ner_modes:
        ner_engine = get_default_ner()
        entities = ner_engine.detect_entities(out, labels=ner_modes)
        for ent in entities:
            if ent.label not in found:
                found.append(ent.label)
            out = out.replace(ent.text, f"[REDACTED_{ent.label.upper()}]")
            
    return out, found


def pseudonymize_string(
    value: str, modes: List[str] | None = None
) -> Tuple[str, Dict[str, str], List[str]]:
    """Replace sensitive entities with reversible tokens and return the mapping.

    Returns:
        (pseudonymized_text, {token: original_value}, list_of_modes_found)
    """
    modes = modes if modes is not None else _active_modes()
    token_map: Dict[str, str] = {}
    found: List[str] = []
    out = value
    counters: Dict[str, int] = {}

    for mode in modes:
        if mode not in _PATTERNS:
            continue
        pat, _ = _PATTERNS[mode]

        def _repl(match: re.Match) -> str:
            matched_str = match.group(0)
            if mode not in found:
                found.append(mode)
            counters[mode] = counters.get(mode, 0) + 1
            token = f"[KM_{mode.upper()}_{counters[mode]}]"
            token_map[token] = matched_str
            return token

        out = pat.sub(_repl, out)

    ner_modes = [m for m in modes if m in NER_MODES]
    if ner_modes:
        ner_engine = get_default_ner()
        entities = ner_engine.detect_entities(out, labels=ner_modes)
        for ent in entities:
            mode = ent.label
            if mode not in found:
                found.append(mode)
            counters[mode] = counters.get(mode, 0) + 1
            token = f"[KM_{mode.upper()}_{counters[mode]}]"
            token_map[token] = ent.text
            out = out.replace(ent.text, token)

    return out, token_map, found


def restore_string(text: str, token_map: Dict[str, str]) -> str:
    """Swap tokens back to their original values in the output text."""
    if not text or not token_map:
        return text
    out = text
    for token, original in token_map.items():
        out = out.replace(token, original)
    return out


def _walk(obj: Any, modes: List[str], found: List[str]) -> Any:
    if isinstance(obj, str):
        text, hits = redact_string(obj, modes)
        for h in hits:
            if h not in found:
                found.append(h)
        return text
    if isinstance(obj, dict):
        return {k: _walk(v, modes, found) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk(v, modes, found) for v in obj]
    return obj


def redact_attributes(attributes: Dict[str, Any] | None) -> Tuple[Dict[str, Any], List[str]]:
    """Redact nested attribute values. Returns (attrs, redacted_fields/modes)."""
    if not _enabled():
        return dict(attributes or {}), []
    modes = _active_modes()
    found: List[str] = []
    cleaned = _walk(dict(attributes or {}), modes, found)
    if found:
        cleaned = dict(cleaned)
        cleaned["attributes_redacted_fields"] = list(found)
    return cleaned, found
