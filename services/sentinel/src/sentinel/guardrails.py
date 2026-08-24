"""Prompt injection heuristics.

The implementation moved to ``kubemind_policy`` so the router scores the same
way inline. This module re-exports it to keep sentinel's imports stable.
"""

from kubemind_policy.guardrails import (  # noqa: F401
    annotate_attributes,
    extract_text_from_attributes,
    score_injection,
)

__all__ = [
    "annotate_attributes",
    "extract_text_from_attributes",
    "score_injection",
]
