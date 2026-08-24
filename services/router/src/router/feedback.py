"""Free labels harvested from production traffic.

Three things the router already knows are exactly the cases a labelled set is
short of, and they cost nothing to collect:

* **abstentions** -- the classifier declined to choose, so the example sits on
  a decision boundary
* **low-confidence predictions** -- above the threshold but only just
* **provider fallbacks** -- the first choice failed, which is evidence the
  profile's pool ordering is wrong for this kind of prompt

Hand-labelling a random sample teaches the classifier mostly what it already
knows. These three are the sample worth a human's attention.

Two constraints shape the implementation:

* **Prompts are redacted before they are written.** A review queue is a second
  copy of user traffic in a place nobody is watching. Anything the policy
  engine flags as sensitive is dropped entirely rather than redacted, because
  a redacted secret is still evidence a secret was sent.
* **Predictions are never fed back as labels.** Reviewed cases are exported in
  the eval dataset's format for a human to confirm. Training on your own
  output compounds error with no signal that anything is wrong.
"""

from __future__ import annotations

import json
import time
import uuid
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

from kubemind_policy import redaction

REASON_ABSTENTION = "abstention"
REASON_LOW_CONFIDENCE = "low_confidence"
REASON_FALLBACK = "provider_fallback"
REASON_POLICY_OVERRIDE = "policy_override"


@dataclass
class FeedbackConfig:
    enabled: bool = True
    # Anything above this was a confident call and is not worth a human's time.
    low_confidence_threshold: float = 0.55
    max_prompt_chars: int = 400
    # Cap the queue so an unreviewed backlog cannot grow without bound.
    max_cases: int = 2000
    ttl_seconds: int = 60 * 60 * 24 * 30
    # Sensitive prompts are never queued, redacted or otherwise.
    skip_sensitive: bool = True

    @classmethod
    def from_config(cls, config: Optional[Dict[str, Any]]) -> "FeedbackConfig":
        cfg = ((config or {}).get("routing") or {}).get("feedback") or {}
        return cls(
            enabled=bool(cfg.get("enabled", True)),
            low_confidence_threshold=float(cfg.get("low_confidence_threshold", 0.55)),
            max_prompt_chars=int(cfg.get("max_prompt_chars", 400)),
            max_cases=int(cfg.get("max_cases", 2000)),
            ttl_seconds=int(cfg.get("ttl_seconds", 60 * 60 * 24 * 30)),
            skip_sensitive=bool(cfg.get("skip_sensitive", True)),
        )


@dataclass
class FeedbackCase:
    case_id: str
    workspace_id: str
    reason: str
    prompt: str
    predicted_intent: str
    confidence: float
    margin: float
    scores: Dict[str, float]
    profile: str
    provider: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    reviewed_intent: Optional[str] = None
    reviewed_at: Optional[float] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "workspace_id": self.workspace_id,
            "reason": self.reason,
            "prompt": self.prompt,
            "predicted_intent": self.predicted_intent,
            "confidence": round(self.confidence, 4),
            "margin": round(self.margin, 4),
            "scores": {k: round(v, 4) for k, v in (self.scores or {}).items()},
            "profile": self.profile,
            "provider": self.provider,
            "created_at": self.created_at,
            "reviewed_intent": self.reviewed_intent,
            "reviewed_at": self.reviewed_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FeedbackCase":
        return cls(
            case_id=d["case_id"],
            workspace_id=d.get("workspace_id", "default"),
            reason=d.get("reason", REASON_LOW_CONFIDENCE),
            prompt=d.get("prompt", ""),
            predicted_intent=d.get("predicted_intent", "general"),
            confidence=float(d.get("confidence", 0.0)),
            margin=float(d.get("margin", 0.0)),
            scores=d.get("scores") or {},
            profile=d.get("profile", "general"),
            provider=d.get("provider"),
            created_at=float(d.get("created_at", time.time())),
            reviewed_intent=d.get("reviewed_intent"),
            reviewed_at=d.get("reviewed_at"),
        )


class FeedbackLog:
    """Queue of cases worth a human's attention.

    Redis-backed so it survives a restart and is shared across replicas, with
    an in-process deque fallback so a router without Redis still works.
    """

    def __init__(
        self,
        redis_client=None,
        config: Optional[FeedbackConfig] = None,
    ):
        self.client = redis_client
        self.config = config or FeedbackConfig()
        self._memory: Deque[FeedbackCase] = deque(maxlen=self.config.max_cases)
        # Rolling intent counts, for drift. Distributions move as partners
        # start using the system for things it was not tuned on.
        self._distribution: Counter = Counter()
        self._total_seen = 0

    def _key(self, workspace_id: str) -> str:
        return f"km:feedback:{workspace_id}"

    def should_capture(
        self,
        *,
        abstained: bool,
        confidence: float,
        used_fallback: bool,
        policy_action: str = "allow",
    ) -> Optional[str]:
        """Which of the three signals fired, if any."""
        if not self.config.enabled:
            return None
        if abstained:
            return REASON_ABSTENTION
        if used_fallback:
            return REASON_FALLBACK
        if confidence < self.config.low_confidence_threshold:
            return REASON_LOW_CONFIDENCE
        if policy_action in ("block", "local_only"):
            return REASON_POLICY_OVERRIDE
        return None

    async def capture(
        self,
        *,
        workspace_id: str,
        reason: str,
        prompt: str,
        predicted_intent: str,
        confidence: float,
        margin: float,
        scores: Optional[Dict[str, float]] = None,
        profile: str = "general",
        provider: Optional[str] = None,
        sensitive: bool = False,
    ) -> Optional[FeedbackCase]:
        if not self.config.enabled or not prompt:
            return None

        # A redacted secret is still evidence a secret was sent, so sensitive
        # prompts are dropped rather than scrubbed.
        if sensitive and self.config.skip_sensitive:
            return None
        detectors = redaction.detect(prompt)
        if detectors and self.config.skip_sensitive:
            return None

        redacted, _ = redaction.redact_string(prompt[: self.config.max_prompt_chars])

        case = FeedbackCase(
            case_id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            reason=reason,
            prompt=redacted,
            predicted_intent=predicted_intent,
            confidence=confidence,
            margin=margin,
            scores=scores or {},
            profile=profile,
            provider=provider,
        )

        if self.client:
            try:
                key = self._key(workspace_id)
                await self.client.lpush(key, json.dumps(case.as_dict()))
                await self.client.ltrim(key, 0, self.config.max_cases - 1)
                await self.client.expire(key, self.config.ttl_seconds)
                return case
            except Exception:
                # Never let label collection break a request.
                pass

        self._memory.appendleft(case)
        return case

    def observe(self, intent: str):
        """Record a prediction for drift tracking, reviewed or not."""
        self._distribution[intent] += 1
        self._total_seen += 1

    async def pending(
        self,
        workspace_id: str,
        limit: int = 50,
        reason: Optional[str] = None,
        include_reviewed: bool = False,
    ) -> List[Dict[str, Any]]:
        cases = await self._all(workspace_id)
        out = []
        for case in cases:
            if reason and case.reason != reason:
                continue
            if not include_reviewed and case.reviewed_intent:
                continue
            out.append(case.as_dict())
            if len(out) >= limit:
                break
        return out

    async def _all(self, workspace_id: str) -> List[FeedbackCase]:
        if self.client:
            try:
                raw = await self.client.lrange(self._key(workspace_id), 0, -1)
                cases = []
                for item in raw or []:
                    if isinstance(item, bytes):
                        item = item.decode()
                    cases.append(FeedbackCase.from_dict(json.loads(item)))
                return cases
            except Exception:
                return []
        return [c for c in self._memory if c.workspace_id == workspace_id]

    async def review(
        self, workspace_id: str, case_id: str, true_intent: str
    ) -> Optional[Dict[str, Any]]:
        """Attach a human label to a case."""
        if self.client:
            try:
                key = self._key(workspace_id)
                raw = await self.client.lrange(key, 0, -1)
                for idx, item in enumerate(raw or []):
                    if isinstance(item, bytes):
                        item = item.decode()
                    data = json.loads(item)
                    if data.get("case_id") != case_id:
                        continue
                    data["reviewed_intent"] = true_intent
                    data["reviewed_at"] = time.time()
                    await self.client.lset(key, idx, json.dumps(data))
                    return data
                return None
            except Exception:
                return None

        for case in self._memory:
            if case.case_id == case_id and case.workspace_id == workspace_id:
                case.reviewed_intent = true_intent
                case.reviewed_at = time.time()
                return case.as_dict()
        return None

    async def export_jsonl(self, workspace_id: str) -> str:
        """Reviewed cases in eval/dataset.jsonl format.

        Human-confirmed labels only. Exporting predictions would let the
        classifier grade its own homework.
        """
        lines = []
        for case in await self._all(workspace_id):
            if not case.reviewed_intent:
                continue
            lines.append(
                json.dumps(
                    {
                        "prompt": case.prompt,
                        "intent": case.reviewed_intent,
                        "source": f"production:{case.reason}",
                    }
                )
            )
        return "\n".join(lines)

    async def summary(self, workspace_id: str) -> Dict[str, Any]:
        cases = await self._all(workspace_id)
        by_reason: Counter = Counter(c.reason for c in cases)
        reviewed = [c for c in cases if c.reviewed_intent]
        disagreements = [
            c for c in reviewed if c.reviewed_intent != c.predicted_intent
        ]

        total = sum(self._distribution.values())
        distribution = (
            {k: round(v / total, 4) for k, v in self._distribution.most_common()}
            if total
            else {}
        )

        return {
            "workspace_id": workspace_id,
            "pending": len(cases) - len(reviewed),
            "reviewed": len(reviewed),
            "by_reason": dict(by_reason),
            # The number to watch. A rising disagreement rate means the intent
            # definitions no longer match what people are actually asking for.
            "disagreement_rate": (
                round(len(disagreements) / len(reviewed), 4) if reviewed else None
            ),
            "confusions": dict(
                Counter(
                    f"{c.predicted_intent}->{c.reviewed_intent}" for c in disagreements
                )
            ),
            "live_intent_distribution": distribution,
            "requests_observed": self._total_seen,
        }
