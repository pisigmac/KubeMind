"""Document chunking for knowledge ingest."""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional


def _load_chunk_config() -> Dict:
    """Best-effort load from env; knowledge.yaml values applied by caller when available."""
    return {
        "max_tokens": int(os.environ.get("CHUNK_MAX_TOKENS", "512")),
        "overlap_tokens": int(os.environ.get("CHUNK_OVERLAP_TOKENS", "64")),
        "strategy": os.environ.get("CHUNK_STRATEGY", "recursive_character"),
    }


def tokens_to_chars(tokens: int) -> int:
    """Rough token→char estimate for Latin text."""
    return max(64, tokens * 4)


def chunk_text(
    text: str,
    *,
    max_tokens: int = 512,
    overlap_tokens: int = 64,
    strategy: str = "recursive_character",
) -> List[str]:
    """Split text into overlapping chunks.

    Uses character windows sized from token estimates. Separators prefer
    paragraph/line/word boundaries for ``recursive_character``.
    """
    if not text or not text.strip():
        return []

    max_chars = tokens_to_chars(max_tokens)
    overlap_chars = tokens_to_chars(overlap_tokens)
    if len(text) <= max_chars:
        return [text.strip()]

    if strategy == "fixed":
        return _fixed_windows(text, max_chars, overlap_chars)

    return _recursive_character(text, max_chars, overlap_chars)


def _fixed_windows(text: str, max_chars: int, overlap_chars: int) -> List[str]:
    chunks: List[str] = []
    start = 0
    step = max(1, max_chars - overlap_chars)
    while start < len(text):
        end = min(len(text), start + max_chars)
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start += step
    return chunks


def _recursive_character(text: str, max_chars: int, overlap_chars: int) -> List[str]:
    separators = ["\n\n", "\n", ". ", " ", ""]
    return _split_recursive(text, max_chars, overlap_chars, separators)


def _split_recursive(
    text: str, max_chars: int, overlap_chars: int, separators: List[str]
) -> List[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    sep = separators[0] if separators else ""
    rest_seps = separators[1:] if len(separators) > 1 else [""]

    if sep == "":
        return _fixed_windows(text, max_chars, overlap_chars)

    parts = text.split(sep)
    chunks: List[str] = []
    current = ""

    for i, part in enumerate(parts):
        candidate = part if not current else current + sep + part
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.extend(_split_recursive(current, max_chars, overlap_chars, rest_seps))
            current = ""

        if len(part) > max_chars:
            chunks.extend(_split_recursive(part, max_chars, overlap_chars, rest_seps))
        else:
            current = part

    if current:
        chunks.extend(_split_recursive(current, max_chars, overlap_chars, rest_seps))

    # Apply overlap by merging tails when chunks are adjacent and short of max
    if overlap_chars > 0 and len(chunks) > 1:
        overlapped: List[str] = [chunks[0]]
        for ch in chunks[1:]:
            prev = overlapped[-1]
            tail = prev[-overlap_chars:] if len(prev) > overlap_chars else prev
            merged = (tail + "\n" + ch).strip()
            if len(merged) <= max_chars + overlap_chars:
                overlapped.append(merged if not ch.startswith(tail) else ch)
            else:
                overlapped.append(ch)
        return [c for c in overlapped if c.strip()]

    return chunks


def expand_nodes_with_chunks(
    nodes: List[Dict],
    *,
    max_tokens: int = 512,
    overlap_tokens: int = 64,
    strategy: str = "recursive_character",
) -> List[Dict]:
    """Expand each node into one or more chunk nodes with parent metadata."""
    import uuid

    expanded: List[Dict] = []
    for node in nodes:
        content = node.get("content") or ""
        pieces = chunk_text(
            content,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            strategy=strategy,
        )
        if not pieces:
            continue
        parent_id = node.get("id") or str(uuid.uuid4())
        if len(pieces) == 1:
            n = dict(node)
            n["id"] = parent_id
            n["content"] = pieces[0]
            meta = dict(n.get("metadata") or {})
            meta["chunk_index"] = 0
            meta["chunk_total"] = 1
            n["metadata"] = meta
            expanded.append(n)
            continue

        for idx, piece in enumerate(pieces):
            n = dict(node)
            n["id"] = str(uuid.uuid4())
            n["content"] = piece
            meta = dict(n.get("metadata") or {})
            meta["parent_id"] = parent_id
            meta["chunk_index"] = idx
            meta["chunk_total"] = len(pieces)
            n["metadata"] = meta
            expanded.append(n)
    return expanded
