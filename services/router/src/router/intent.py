"""Intent classification for prompt routing.

Two layers, deliberately:

* **Rules** are a high-precision prior. They fire on unambiguous signals and
  nudge the semantic score; a small set of them are hard overrides.
* **k-NN over example embeddings** carries the generalisation. Centroids were
  rejected because an intent like ``code`` is genuinely multi-modal -- write,
  debug and explain sit in different regions and their mean lands between them.

Confidence is the *margin* between the top two intents, not raw similarity.
Embedding spaces are anisotropic and everything sits at 0.5-0.8 similarity to
everything, so absolute similarity says little about whether we are sure. Below
threshold the classifier abstains to ``general`` rather than guessing.

This classifier never gates a governance decision. See ``router.policy``.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

GENERAL = "general"

# Reserved intent name for the decoy class. Prompts that land here are
# out-of-distribution and get treated as `general`, but having somewhere for
# them to go stops them being forced into the nearest real intent.
BACKGROUND = "_background"


# ── Rule layer ───────────────────────────────────────────────────
# Narrowed from keyword soup to phrases that are actually discriminative.
# The old patterns matched bare tokens like `api` and `sdk`, which appear in
# plenty of prompts that have nothing to do with writing code.
_RULES: Dict[str, re.Pattern] = {
    "code": re.compile(
        r"\b(refactor|implement|debug|stack\s?trace|compile|unit\s?test|"
        r"function|classes?|docstring|type\s?error|syntax|snippet|"
        r"python|typescript|golang|rust|java|sql)\b",
        re.I,
    ),
    "rag": re.compile(
        r"\b(according\s+to|per\s+(the|our)|look\s?up|search\s+(the|our)|"
        r"knowledge\s?base|handbook|wiki|runbook|documentation|"
        r"what\s+does\s+(the|our)\s+\w+\s+say|cite|soc2|policy\s+document)\b",
        re.I,
    ),
    "security": re.compile(
        r"\b(vulnerabilit|cve-?\d|exploit|threat\s?model|malware|"
        r"penetration\s?test|rbac|mtls|attack\s?surface|hardening|"
        r"pii|pci-?dss|gdpr|sanitiz|credential\s+rotation|"
        r"injection\s+attacks?|security\s+(review|audit|scan))\b",
        re.I,
    ),
    "log": re.compile(
        r"\b(crashloop|oom\s?killed|stack\s?trace|stderr|stdout|"
        r"error\s?rate|log\s?lines?|summari[sz]e\s+(the\s+)?logs?|"
        r"why\s+is\s+.{0,20}(failing|restarting|crashing))\b",
        re.I,
    ),
}

# Hard overrides: when one of these fires the intent is settled and the
# semantic layer is not consulted. Kept deliberately small.
_HARD_OVERRIDES: Dict[str, re.Pattern] = {
    "log": re.compile(r"\b(crashloop(back\s?off)?|oom\s?killed)\b", re.I),
    "security": re.compile(r"\bcve-\d{4}-\d{4,}\b", re.I),
}


def rule_scores(text: str) -> Dict[str, float]:
    """Normalised 0..1 rule score per intent."""
    if not text:
        return {}
    out: Dict[str, float] = {}
    for intent, pat in _RULES.items():
        hits = len(pat.findall(text))
        if hits:
            # Saturating: three distinct hits is as confident as the rules get.
            out[intent] = min(1.0, hits / 3.0)
    return out


def hard_override(text: str) -> Optional[str]:
    if not text:
        return None
    for intent, pat in _HARD_OVERRIDES.items():
        if pat.search(text):
            return intent
    return None


# ── Text selection ───────────────────────────────────────────────

def select_classification_text(
    messages: Sequence[Any],
    *,
    history_decay: float = 0.35,
    max_history_turns: int = 3,
    max_chars: int = 4000,
) -> str:
    """Build the text to classify from a chat transcript.

    The latest user turn carries the intent. Earlier turns are included at
    reduced weight (by truncation, since we cannot weight tokens directly)
    because they add useful context but should not outvote the current ask.
    System prompts are excluded: they are constant per application and would
    dominate every vector with the same content.
    """
    user_turns: List[str] = []
    for m in messages:
        role = m.role if hasattr(m, "role") else m.get("role")
        content = m.content if hasattr(m, "content") else m.get("content")
        if role == "user" and content:
            user_turns.append(str(content))

    if not user_turns:
        return ""

    latest = user_turns[-1]
    if len(user_turns) == 1 or history_decay <= 0:
        return latest[:max_chars]

    budget = max(0, int(max_chars * history_decay))
    history: List[str] = []
    for turn in reversed(user_turns[:-1][-max_history_turns:]):
        if budget <= 0:
            break
        history.append(turn[:budget])
        budget -= len(turn[:budget])

    parts = list(reversed(history)) + [latest]
    return "\n".join(parts)[:max_chars]


def extract_user_text(messages: Sequence[Any]) -> str:
    """Join user message contents.

    Retained for callers that want the full transcript (the semantic cache key
    and the sensitivity pass both want everything the user actually sent, not
    the truncated view the classifier uses).
    """
    parts = []
    for m in messages:
        role = m.role if hasattr(m, "role") else m.get("role")
        content = m.content if hasattr(m, "content") else m.get("content")
        if role == "user" and content:
            parts.append(str(content))
    return "\n".join(parts) if parts else ""


# ── Vector helpers ───────────────────────────────────────────────

def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = na = nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


# ── Result ───────────────────────────────────────────────────────

@dataclass
class IntentResult:
    intent: str
    confidence: float
    margin: float
    method: str  # rules | hard_override | knn | hybrid | abstain | disabled
    scores: Dict[str, float] = field(default_factory=dict)
    abstained: bool = False

    def as_attributes(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "intent_confidence": round(self.confidence, 4),
            "intent_margin": round(self.margin, 4),
            "intent_method": self.method,
            "intent_abstained": self.abstained,
        }


@dataclass
class ClassifierConfig:
    enabled: bool = True
    knn_k: int = 3
    margin_threshold: float = 0.02
    min_similarity: float = 0.45
    temperature: float = 0.05
    rule_prior_weight: float = 0.06
    history_decay: float = 0.35

    @classmethod
    def from_dict(cls, raw: Dict[str, Any] | None) -> "ClassifierConfig":
        raw = raw or {}
        return cls(
            enabled=bool(raw.get("enabled", True)),
            knn_k=int(raw.get("knn_k", 3)),
            margin_threshold=float(raw.get("margin_threshold", 0.02)),
            min_similarity=float(raw.get("min_similarity", 0.45)),
            temperature=float(raw.get("temperature", 0.05)),
            rule_prior_weight=float(raw.get("rule_prior_weight", 0.06)),
            history_decay=float(raw.get("history_decay", 0.35)),
        )


class IntentClassifier:
    """Hybrid rule + k-NN intent classifier.

    The index is built once at startup by embedding the configured examples.
    If the embedder is unavailable the classifier degrades to rules only rather
    than failing the request: a broken Ollama should cost routing quality, not
    availability.
    """

    def __init__(
        self,
        config: Optional[ClassifierConfig] = None,
        examples: Optional[Dict[str, List[str]]] = None,
    ):
        self.config = config or ClassifierConfig()
        self.examples: Dict[str, List[str]] = examples or {}
        # intent -> list of example vectors
        self.index: Dict[str, List[List[float]]] = {}
        self.is_ready = False

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "IntentClassifier":
        routing = (config or {}).get("routing", {}) or {}
        cfg = ClassifierConfig.from_dict(routing.get("classifier"))
        cfg.enabled = cfg.enabled and bool(routing.get("intent_enabled", True))

        examples: Dict[str, List[str]] = {}
        for name, spec in (routing.get("intents") or {}).items():
            if isinstance(spec, dict):
                ex = spec.get("examples") or []
            else:
                ex = list(spec or [])
            if ex:
                examples[name] = [str(e) for e in ex]
        return cls(config=cfg, examples=examples)

    @property
    def intents(self) -> List[str]:
        return [i for i in self.examples if i != BACKGROUND]

    async def build_index(
        self, embed: Callable[[str], Awaitable[Optional[List[float]]]]
    ) -> int:
        """Embed every configured example. Returns the number indexed."""
        if not self.config.enabled or not self.examples:
            return 0
        indexed = 0
        for intent, texts in self.examples.items():
            vectors: List[List[float]] = []
            for text in texts:
                try:
                    vec = await embed(text)
                except Exception:
                    vec = None
                if vec:
                    vectors.append(vec)
            if vectors:
                self.index[intent] = vectors
                indexed += len(vectors)
        self.is_ready = bool(self.index)
        return indexed

    def _knn_scores(self, embedding: Sequence[float]) -> Dict[str, float]:
        """Score per intent: mean of that intent's top-k example similarities.

        Scoring within each intent rather than globally keeps intents with many
        examples from crowding out intents with few.
        """
        scores: Dict[str, float] = {}
        k = max(1, self.config.knn_k)
        for intent, vectors in self.index.items():
            sims = sorted(
                (cosine_similarity(embedding, v) for v in vectors), reverse=True
            )
            if not sims:
                continue
            top = sims[: min(k, len(sims))]
            scores[intent] = sum(top) / len(top)
        return scores

    def _confidence(self, scores: Dict[str, float], top: str) -> float:
        """Softmax over intent scores at the configured temperature."""
        if not scores:
            return 0.0
        t = max(1e-6, self.config.temperature)
        exps = {k: math.exp(v / t) for k, v in scores.items()}
        total = sum(exps.values())
        if total <= 0:
            return 0.0
        return exps.get(top, 0.0) / total

    def classify(
        self,
        text: str,
        embedding: Optional[Sequence[float]] = None,
    ) -> IntentResult:
        if not self.config.enabled:
            return IntentResult(GENERAL, 1.0, 1.0, "disabled")
        if not text or not text.strip():
            return IntentResult(GENERAL, 1.0, 1.0, "abstain", abstained=True)

        forced = hard_override(text)
        if forced:
            return IntentResult(forced, 1.0, 1.0, "hard_override")

        rules = rule_scores(text)

        # No usable index: rules only.
        if not embedding or not self.index:
            if not rules:
                return IntentResult(GENERAL, 0.0, 0.0, "rules", abstained=True)
            ordered = sorted(rules.items(), key=lambda kv: kv[1], reverse=True)
            top, top_score = ordered[0]
            runner_up = ordered[1][1] if len(ordered) > 1 else 0.0
            margin = top_score - runner_up
            if margin <= 0:
                # Genuine tie in the rule layer. Abstaining is the honest
                # answer; picking by dict order is what the old code did.
                return IntentResult(
                    GENERAL, 0.0, 0.0, "rules", scores=rules, abstained=True
                )
            return IntentResult(top, top_score, margin, "rules", scores=rules)

        scores = self._knn_scores(embedding)
        if not scores:
            return IntentResult(GENERAL, 0.0, 0.0, "abstain", abstained=True)

        # Rules act as a prior: a small additive bonus where they agree.
        method = "knn"
        if rules:
            method = "hybrid"
            for intent, rscore in rules.items():
                if intent in scores:
                    scores[intent] += self.config.rule_prior_weight * rscore

        ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        top, top_score = ordered[0]
        runner_up = ordered[1][1] if len(ordered) > 1 else 0.0
        margin = top_score - runner_up
        confidence = self._confidence(scores, top)

        if top == BACKGROUND:
            return IntentResult(
                GENERAL, confidence, margin, method, scores=scores, abstained=True
            )
        if top_score < self.config.min_similarity:
            return IntentResult(
                GENERAL, confidence, margin, method, scores=scores, abstained=True
            )
        if margin < self.config.margin_threshold:
            return IntentResult(
                GENERAL, confidence, margin, method, scores=scores, abstained=True
            )

        return IntentResult(top, confidence, margin, method, scores=scores)


# ── Backwards-compatible helper ──────────────────────────────────

def classify_intent(text: str) -> str:
    """Rules-only classification.

    Kept for callers that have no embedding to hand. Returns ``general`` when
    the rules are silent or tie.
    """
    return IntentClassifier().classify(text).intent
