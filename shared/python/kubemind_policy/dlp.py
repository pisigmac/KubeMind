"""Custom Enterprise Data Loss Prevention (DLP) & Proprietary Wordmask Engine.

Enables workspaces to define proprietary keywords, internal project codenames,
and custom organizational regex patterns that are pseudonymized alongside PII.
"""

from __future__ import annotations

import re
from typing import Dict, List, Pattern, Set, Tuple


class CustomDLPEngine:
    """Workspace-scoped custom DLP and proprietary terminology masking engine."""

    def __init__(self):
        # workspace_id -> set of exact keywords/phrases
        self._keywords: Dict[str, Set[str]] = {}
        # workspace_id -> list of compiled regex patterns
        self._patterns: Dict[str, List[Pattern]] = {}

    def register_keywords(self, workspace_id: str, keywords: List[str]) -> None:
        """Register proprietary keywords or codenames for a workspace."""
        if workspace_id not in self._keywords:
            self._keywords[workspace_id] = set()
        for kw in keywords:
            cleaned = kw.strip()
            if cleaned:
                self._keywords[workspace_id].add(cleaned)

    def register_patterns(self, workspace_id: str, regexes: List[str]) -> None:
        """Register custom DLP regex patterns for a workspace."""
        if workspace_id not in self._patterns:
            self._patterns[workspace_id] = []
        for r in regexes:
            try:
                compiled = re.compile(r, re.IGNORECASE)
                self._patterns[workspace_id].append(compiled)
            except re.error:
                continue

    def mask_text(
        self, text: str, workspace_id: str = "default", start_idx: int = 1
    ) -> Tuple[str, Dict[str, str], List[str]]:
        """
        Mask proprietary phrases and regex patterns with reversible `[KM_DLP_N]` tokens.
        Returns: (masked_text, token_map, hits_list)
        """
        if not text:
            return text, {}, []

        token_map: Dict[str, str] = {}
        hits: List[str] = []
        result = text
        token_counter = start_idx

        # 1. Custom Regex Patterns
        patterns = self._patterns.get(workspace_id, [])
        for pat in patterns:
            matches = list(pat.finditer(result))
            for match in matches:
                matched_str = match.group(0)
                if matched_str not in token_map.values():
                    token = f"[KM_DLP_{token_counter}]"
                    token_counter += 1
                    token_map[token] = matched_str
                    hits.append("custom_pattern")
                    result = result.replace(matched_str, token)

        # 2. Exact Keywords / Codenames (longest first to avoid substring clipping)
        keywords = sorted(
            list(self._keywords.get(workspace_id, set())), key=len, reverse=True
        )
        for kw in keywords:
            if kw.lower() in result.lower():
                # Case-insensitive replacement preserving original match
                pattern = re.compile(re.escape(kw), re.IGNORECASE)
                match = pattern.search(result)
                if match:
                    original_val = match.group(0)
                    if original_val not in token_map.values():
                        token = f"[KM_DLP_{token_counter}]"
                        token_counter += 1
                        token_map[token] = original_val
                        hits.append("proprietary_codeword")
                        result = pattern.sub(token, result)

        return result, token_map, hits


_GLOBAL_DLP = CustomDLPEngine()


def get_default_dlp() -> CustomDLPEngine:
    return _GLOBAL_DLP
