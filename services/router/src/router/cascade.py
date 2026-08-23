"""Optional escalation cascade.

Try a cheap local target first; escalate to a stronger model when the
classifier is unsure or the first answer looks thin. High value only after
the evaluation set exists to prove it helps -- which is why this is opt-in
and off by default.

Escalation never overrides a `local_only` policy verdict. Governance stays
independent of intent confidence here too.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class CascadeConfig:
    enabled: bool = False
    # Escalate when intent confidence is below this (and not abstained into
    # general by design -- abstention already picked the general profile).
    confidence_below: float = 0.55
    # Escalate when the first answer is shorter than this many characters.
    min_answer_chars: int = 40
    # Escalation pool, in preference order. Empty means "the rest of the
    # eligible chain after the first attempt".
    escalate_pool: List[str] = field(default_factory=list)
    # Prefer local providers for the first attempt even if the profile pool
    # lists a cloud provider first.
    prefer_local_first: bool = True

    @classmethod
    def from_dict(cls, raw: Optional[Dict[str, Any]]) -> "CascadeConfig":
        raw = raw or {}
        pool = raw.get("escalate_pool") or []
        if isinstance(pool, str):
            pool = [pool]
        return cls(
            enabled=bool(raw.get("enabled", False)),
            confidence_below=float(raw.get("confidence_below", 0.55)),
            min_answer_chars=int(raw.get("min_answer_chars", 40)),
            escalate_pool=[str(p) for p in pool],
            prefer_local_first=bool(raw.get("prefer_local_first", True)),
        )


@dataclass
class CascadeDecision:
    should_escalate: bool
    reason: Optional[str] = None

    def as_attributes(self) -> Dict[str, Any]:
        return {
            "cascade_escalated": self.should_escalate,
            "cascade_reason": self.reason,
        }


def should_escalate(
    *,
    config: CascadeConfig,
    confidence: float,
    abstained: bool,
    answer_text: str,
    local_only: bool,
) -> CascadeDecision:
    """Decide whether the first answer should be replaced by an escalation.

    `local_only` always wins: escalating to a cloud provider would defeat the
    sensitivity verdict, so the cascade refuses that path outright.
    """
    if not config.enabled:
        return CascadeDecision(False)
    if local_only:
        return CascadeDecision(False, reason="local_only_blocks_escalation")

    if abstained or confidence < config.confidence_below:
        return CascadeDecision(True, reason="low_confidence")

    text = (answer_text or "").strip()
    if len(text) < config.min_answer_chars:
        return CascadeDecision(True, reason="thin_answer")

    return CascadeDecision(False)


def reorder_for_cascade(
    chain: Sequence[Any],
    *,
    config: CascadeConfig,
    is_local,
) -> List[Any]:
    """Put a local provider first when cascade prefers local-first.

    The rest of the chain stays as the escalation path. Preserves relative
    order within each group so profile preference is not discarded.
    """
    if not config.enabled or not config.prefer_local_first or not chain:
        return list(chain)
    local = [p for p in chain if is_local(p.name)]
    remote = [p for p in chain if not is_local(p.name)]
    if not local:
        return list(chain)
    return local + remote


def extract_answer_text(response: Dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    return str(msg.get("content") or choices[0].get("text") or "")
