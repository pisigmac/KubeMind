"""Inline sensitivity policy.

Runs in the router *before* dispatch, so a decision can still change what
happens. Sentinel's copy of these detectors runs at span ingest, which is after
the prompt has already reached the provider -- useful for reporting, useless as
a control.

Deliberately independent of the intent classifier. Intent is an optimisation
and is allowed to abstain or be wrong; this is a control and is tuned for
recall. Nothing here reads `IntentResult`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from kubemind_policy import (
    PII_MODES,
    detect,
    redact_string,
    score_injection,
)


class Action(str, Enum):
    ALLOW = "allow"
    REDACT = "redact"
    LOCAL_ONLY = "local_only"
    BLOCK = "block"


# Most restrictive wins when several rules fire.
_SEVERITY = {
    Action.ALLOW: 0,
    Action.REDACT: 1,
    Action.LOCAL_ONLY: 2,
    Action.BLOCK: 3,
}


class PolicyError(Exception):
    """Raised when the engine cannot reach a verdict and fail_closed is set."""


@dataclass
class PolicyVerdict:
    action: Action = Action.ALLOW
    rules: List[str] = field(default_factory=list)
    detectors: List[str] = field(default_factory=list)
    injection_score: float = 0.0
    injection_flags: List[str] = field(default_factory=list)
    text: Optional[str] = None
    redacted: bool = False
    cacheable: bool = True
    reason: Optional[str] = None

    @property
    def local_only(self) -> bool:
        return self.action is Action.LOCAL_ONLY

    @property
    def blocked(self) -> bool:
        return self.action is Action.BLOCK

    @property
    def egress_class(self) -> str:
        return "local_only" if self.local_only else "any"

    def as_attributes(self) -> Dict[str, Any]:
        return {
            "policy_action": self.action.value,
            "policy_rules": list(self.rules),
            "policy_detectors": list(self.detectors),
            "egress_class": self.egress_class,
            "injection_score": self.injection_score,
            "injection_flags": list(self.injection_flags),
            "redacted": self.redacted,
        }


@dataclass
class Rule:
    detector: str
    action: Action
    threshold: Optional[float] = None

    @property
    def name(self) -> str:
        return f"{self.detector}:{self.action.value}"


def _parse_rules(raw: Any) -> List[Rule]:
    rules: List[Rule] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        detector = item.get("detector")
        action = item.get("action")
        if not detector or not action:
            continue
        try:
            parsed = Action(str(action))
        except ValueError:
            continue
        threshold = item.get("threshold")
        rules.append(
            Rule(
                detector=str(detector),
                action=parsed,
                threshold=float(threshold) if threshold is not None else None,
            )
        )
    return rules


class PolicyEngine:
    """Evaluates prompt text against per-workspace sensitivity rules."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        fail_closed: bool = True,
        default_rules: Optional[List[Rule]] = None,
        workspace_rules: Optional[Dict[str, List[Rule]]] = None,
        no_cache_actions: Tuple[Action, ...] = (Action.LOCAL_ONLY, Action.BLOCK),
    ):
        self.enabled = enabled
        self.fail_closed = fail_closed
        self.default_rules = default_rules or []
        self.workspace_rules = workspace_rules or {}
        self.no_cache_actions = no_cache_actions

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "PolicyEngine":
        raw = (config or {}).get("policy", {}) or {}
        workspace_rules = {
            str(ws): _parse_rules((spec or {}).get("rules"))
            for ws, spec in (raw.get("workspaces") or {}).items()
        }
        return cls(
            enabled=bool(raw.get("enabled", True)),
            fail_closed=bool(raw.get("fail_closed", True)),
            default_rules=_parse_rules((raw.get("default") or {}).get("rules")),
            workspace_rules=workspace_rules,
        )

    def rules_for(self, workspace_id: str) -> List[Rule]:
        return self.workspace_rules.get(workspace_id, self.default_rules)

    def evaluate(self, text: str, workspace_id: str = "default") -> PolicyVerdict:
        if not self.enabled:
            return PolicyVerdict(text=text)

        try:
            return self._evaluate(text, workspace_id)
        except Exception as exc:  # pragma: no cover - defensive
            if self.fail_closed:
                raise PolicyError(str(exc)) from exc
            return PolicyVerdict(text=text, reason=f"policy_error: {exc}")

    def _evaluate(self, text: str, workspace_id: str) -> PolicyVerdict:
        rules = self.rules_for(workspace_id)
        if not rules:
            return PolicyVerdict(text=text)

        fired = detect(text)
        injection_score, injection_flags = score_injection(text)

        action = Action.ALLOW
        matched: List[str] = []
        redact_modes: List[str] = []

        for rule in rules:
            if not self._rule_matches(rule, fired, injection_score):
                continue
            matched.append(rule.name)
            if rule.action is Action.REDACT:
                redact_modes.extend(self._modes_for(rule.detector, fired))
            if _SEVERITY[rule.action] > _SEVERITY[action]:
                action = rule.action

        if action is Action.BLOCK:
            return PolicyVerdict(
                action=action,
                rules=matched,
                detectors=fired,
                injection_score=injection_score,
                injection_flags=injection_flags,
                text=None,
                cacheable=False,
                reason=f"blocked by {', '.join(matched)}",
            )

        out_text = text
        redacted = False
        # Redaction still applies underneath a local_only verdict: sending less
        # is better even when the destination is inside the cluster.
        if redact_modes:
            out_text, hits = redact_string(text, sorted(set(redact_modes)))
            redacted = bool(hits)

        return PolicyVerdict(
            action=action,
            rules=matched,
            detectors=fired,
            injection_score=injection_score,
            injection_flags=injection_flags,
            text=out_text,
            redacted=redacted,
            cacheable=action not in self.no_cache_actions,
        )

    @staticmethod
    def _rule_matches(rule: Rule, fired: List[str], injection_score: float) -> bool:
        detector = rule.detector
        if detector == "injection":
            return injection_score >= (rule.threshold if rule.threshold is not None else 0.5)
        if detector == "any_pii":
            return any(m in fired for m in PII_MODES)
        if detector == "any":
            return bool(fired)
        return detector in fired

    @staticmethod
    def _modes_for(detector: str, fired: List[str]) -> List[str]:
        if detector == "any_pii":
            return [m for m in fired if m in PII_MODES]
        if detector == "any":
            return list(fired)
        if detector == "injection":
            return []
        return [detector] if detector in fired else []
