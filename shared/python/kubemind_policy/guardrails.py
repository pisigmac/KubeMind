"""Prompt injection heuristics."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# (flag_name, pattern, weight)
_RULES: List[Tuple[str, re.Pattern, float]] = [
    (
        "ignore_instructions",
        re.compile(r"(?i)\b(ignore|disregard|forget)\b.{0,40}\b(previous|prior|above|system)\b.{0,20}\b(instructions?|rules?|prompts?)\b"),
        0.35,
    ),
    (
        "reveal_system",
        re.compile(r"(?i)\b(reveal|show|print|dump|leak)\b.{0,30}\b(system\s*prompt|hidden\s*instructions?|developer\s*message)\b"),
        0.4,
    ),
    (
        "jailbreak",
        re.compile(r"(?i)\b(jailbreak|DAN\s*mode|do\s*anything\s*now|no\s*restrictions?)\b"),
        0.35,
    ),
    (
        "exfiltrate",
        re.compile(r"(?i)\b(exfiltrat|send\s+(all|the)\s+(data|secrets?|keys?)|upload\s+to\s+http)\b"),
        0.3,
    ),
    (
        "role_override",
        re.compile(r"(?i)\b(you\s+are\s+now|act\s+as|pretend\s+to\s+be)\b.{0,40}\b(unrestricted|evil|hacker)\b"),
        0.25,
    ),
    (
        "delimiter_injection",
        re.compile(r"(?i)(```system|<\s*/?\s*system\s*>|\[SYSTEM\]|INST\]|<<SYS>>)"),
        0.2,
    ),
]


def score_injection(text: str) -> Tuple[float, List[str]]:
    """Return (score 0..1, flags[])."""
    if not text or not str(text).strip():
        return 0.0, []
    flags: List[str] = []
    score = 0.0
    for name, pat, weight in _RULES:
        if pat.search(text):
            flags.append(name)
            score += weight
    return min(1.0, round(score, 4)), flags


def extract_text_from_attributes(attributes: Dict[str, Any] | None) -> str:
    """Pull likely prompt/content strings from span attributes."""
    if not attributes:
        return ""
    parts: List[str] = []
    keys = ("prompt", "query", "content", "message", "input", "user_message", "text")
    for k in keys:
        v = attributes.get(k)
        if isinstance(v, str):
            parts.append(v)
    # Also scan nested one level
    for v in attributes.values():
        if isinstance(v, dict):
            for k in keys:
                if isinstance(v.get(k), str):
                    parts.append(v[k])
    return "\n".join(parts)


def annotate_attributes(attributes: Dict[str, Any] | None) -> Dict[str, Any]:
    """Add injection_score and injection_flags to attributes (copy)."""
    attrs = dict(attributes or {})
    text = extract_text_from_attributes(attrs)
    score, flags = score_injection(text)
    attrs["injection_score"] = score
    attrs["injection_flags"] = flags
    return attrs
