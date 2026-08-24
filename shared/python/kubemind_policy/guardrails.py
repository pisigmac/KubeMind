"""Enterprise Prompt Injection & Adversarial Jailbreak Defensive Engine.

Provides multi-layer heuristics, obfuscation decoding, and adversarial pattern
detection to guard against:
- Direct & indirect prompt injections
- Base64/Hex/Rot13 obfuscated payload evasion
- Virtual machine / DAN / Developer mode jailbreaks
- System prompt extraction & delimiter smuggling
"""

from __future__ import annotations

import base64
import binascii
import re
from typing import Any, Dict, List, Set, Tuple

# Advanced adversarial regex patterns: (flag_name, pattern, weight)
_RULES: List[Tuple[str, re.Pattern, float]] = [
    (
        "ignore_instructions",
        re.compile(r"(?i)\b(ignore|disregard|forget|bypass|override|cancel)\b.{0,40}\b(previous|prior|above|system|all)\b.{0,20}\b(instructions?|rules?|prompts?|guidelines?)\b"),
        0.40,
    ),
    (
        "reveal_system",
        re.compile(r"(?i)\b(reveal|show|print|dump|leak|repeat|output|recite)\b.{0,30}\b(system\s*prompt|hidden\s*instructions?|developer\s*message|initial\s*instructions?|system\s*message)\b"),
        0.45,
    ),
    (
        "jailbreak_dan",
        re.compile(r"(?i)\b(jailbreak|DAN\s*mode|do\s*anything\s*now|developer\s*mode\s*enabled|unfiltered\s*mode|no\s*restrictions?|god\s*mode)\b"),
        0.50,
    ),
    (
        "virtual_simulation",
        re.compile(r"(?i)\b(simulate|act\s+as|pretend\s+to\s+be|virtual\s+machine|sandbox\s+environment|fictional\s+story)\b.{0,50}\b(without\s+rules|no\s+safety|unconstrained|bypass)\b"),
        0.35,
    ),
    (
        "exfiltrate",
        re.compile(r"(?i)\b(exfiltrat|send\s+(all|the)\s+(data|secrets?|keys?|tokens?)|upload\s+to\s+https?://|webhook\.site|requestbin)\b"),
        0.40,
    ),
    (
        "role_override",
        re.compile(r"(?i)\b(you\s+are\s+now|act\s+as|pretend\s+to\s+be)\b.{0,40}\b(unrestricted|evil|hacker|adversary|root|admin)\b"),
        0.30,
    ),
    (
        "delimiter_injection",
        re.compile(r"(?i)(```system|<\s*/?\s*system\s*>|\[SYSTEM\]|INST\]|<<SYS>>|human:|assistant:|system:|<\|im_start\|>|<\|im_end\|>)"),
        0.30,
    ),
    (
        "token_smuggling",
        re.compile(r"(?i)\b(base64|rot13|hex|morse\s*code|ciphers?)\b.{0,30}\b(decode|execute|evaluate|run)\b"),
        0.25,
    ),
]


def _decode_potential_base64(text: str) -> List[str]:
    """Extract and decode base64 blobs within text to inspect obfuscated payloads."""
    decoded_snippets: List[str] = []
    # Match potential base64 strings of length >= 16
    candidates = re.findall(r"[A-Za-z0-9+/]{16,}={0,2}", text)
    for cand in candidates:
        try:
            raw = base64.b64decode(cand, validate=True)
            decoded = raw.decode("utf-8", errors="ignore").strip()
            if len(decoded) >= 8 and any(c.isalpha() for c in decoded):
                decoded_snippets.append(decoded)
        except (binascii.Error, ValueError):
            continue
    return decoded_snippets


def score_injection(text: str) -> Tuple[float, List[str]]:
    """
    Evaluates text for injection and jailbreak risk.
    Returns (score 0.0..1.0, list of detected flag names).
    """
    if not text or not str(text).strip():
        return 0.0, []

    flags: Set[str] = set()
    score = 0.0

    # 1. Primary inspection
    for name, pat, weight in _RULES:
        if pat.search(text):
            flags.add(name)
            score += weight

    # 2. Obfuscation inspection (Base64 unpacker)
    decoded_blobs = _decode_potential_base64(text)
    for blob in decoded_blobs:
        for name, pat, weight in _RULES:
            if pat.search(blob):
                flags.add(f"obfuscated_{name}")
                score += weight * 1.2  # Higher penalty for deliberately obfuscated attacks

    return min(1.0, round(score, 4)), sorted(list(flags))


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
