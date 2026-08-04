"""Tests for the hybrid intent classifier.

Uses synthetic orthogonal vectors rather than real embeddings so the tests
assert on classifier logic (margin, abstention, decoy handling) instead of on
the quality of whatever model happens to be running.
"""

import pytest

from router.intent import (
    BACKGROUND,
    ClassifierConfig,
    IntentClassifier,
    IntentResult,
    classify_intent,
    hard_override,
    rule_scores,
    select_classification_text,
)
from router.models import Message


def _vec(*parts: float):
    return list(parts)


@pytest.fixture
def classifier():
    """Three intents on orthogonal axes plus a decoy on a fourth."""
    c = IntentClassifier(
        config=ClassifierConfig(
            knn_k=2,
            margin_threshold=0.05,
            min_similarity=0.5,
            temperature=0.1,
            rule_prior_weight=0.0,
        )
    )
    c.index = {
        "code": [_vec(1, 0, 0, 0), _vec(0.98, 0.05, 0, 0)],
        "rag": [_vec(0, 1, 0, 0), _vec(0.05, 0.98, 0, 0)],
        "log": [_vec(0, 0, 1, 0), _vec(0, 0.05, 0.98, 0)],
        BACKGROUND: [_vec(0, 0, 0, 1), _vec(0.02, 0, 0, 0.99)],
    }
    c.examples = {k: [] for k in c.index}
    c.is_ready = True
    return c


class TestRuleLayer:
    def test_rules_are_narrow(self):
        # The old classifier matched bare `api`/`sdk` and called this code.
        assert "code" not in rule_scores("Our API is documented in the SDK guide")

    def test_rules_still_fire_on_real_code_prompts(self):
        assert "code" in rule_scores("Refactor this Python function")

    def test_hard_override(self):
        assert hard_override("the pod is in CrashLoopBackOff") == "log"
        assert hard_override("does CVE-2024-3094 affect us") == "security"
        assert hard_override("write me a poem") is None

    def test_hard_override_wins_without_embedding(self, classifier):
        result = classifier.classify("pod stuck in CrashLoopBackOff", _vec(1, 0, 0, 0))
        assert result.intent == "log"
        assert result.method == "hard_override"

    def test_rules_only_when_index_empty(self):
        c = IntentClassifier()
        result = c.classify("Refactor this Python function")
        assert result.intent == "code"
        assert result.method == "rules"

    def test_rule_tie_abstains_instead_of_dict_order(self):
        c = IntentClassifier()
        # One hit each for code (refactor) and rag (runbook). The old
        # implementation returned whichever key came first in the dict.
        result = c.classify("Refactor the runbook")
        assert result.abstained is True
        assert result.intent == "general"


class TestKnn:
    def test_confident_match(self, classifier):
        result = classifier.classify("anything", _vec(1, 0, 0, 0))
        assert result.intent == "code"
        assert result.abstained is False
        assert result.margin > 0.05

    def test_scores_every_indexed_intent(self, classifier):
        result = classifier.classify("anything", _vec(0, 1, 0, 0))
        assert result.intent == "rag"
        assert set(result.scores) == {"code", "rag", "log", BACKGROUND}

    def test_ambiguous_prompt_abstains_on_margin(self, classifier):
        # Exactly between code and rag: both score the same, margin is ~0.
        result = classifier.classify("anything", _vec(1, 1, 0, 0))
        assert result.abstained is True
        assert result.intent == "general"

    def test_below_min_similarity_abstains(self, classifier):
        classifier.config.min_similarity = 0.99
        result = classifier.classify("anything", _vec(0.8, 0.6, 0, 0))
        assert result.abstained is True

    def test_decoy_class_absorbs_out_of_distribution(self, classifier):
        result = classifier.classify("anything", _vec(0, 0, 0, 1))
        assert result.intent == "general"
        assert result.abstained is True

    def test_per_intent_scoring_resists_example_imbalance(self, classifier):
        # Flood `rag` with far more examples than `code`. Because each intent is
        # scored on its own top-k, the extra examples must not drown out code.
        classifier.index["rag"] = classifier.index["rag"] + [
            _vec(0.6, 0.5, 0, 0) for _ in range(50)
        ]
        result = classifier.classify("anything", _vec(1, 0, 0, 0))
        assert result.intent == "code"


class TestConfidence:
    def test_confidence_between_zero_and_one(self, classifier):
        result = classifier.classify("anything", _vec(1, 0, 0, 0))
        assert 0.0 <= result.confidence <= 1.0

    def test_clearer_match_is_more_confident(self, classifier):
        sharp = classifier.classify("anything", _vec(1, 0, 0, 0))
        fuzzy = classifier.classify("anything", _vec(1, 0.7, 0, 0))
        assert sharp.confidence > fuzzy.confidence

    def test_margin_reported(self, classifier):
        result = classifier.classify("anything", _vec(1, 0, 0, 0))
        assert result.margin == pytest.approx(
            result.scores["code"] - max(v for k, v in result.scores.items() if k != "code")
        )


class TestDegradation:
    def test_missing_embedding_falls_back_to_rules(self, classifier):
        result = classifier.classify("Refactor this Python function", None)
        assert result.intent == "code"
        assert result.method == "rules"

    def test_disabled_classifier_returns_general(self):
        c = IntentClassifier(config=ClassifierConfig(enabled=False))
        result = c.classify("Refactor this Python function")
        assert result.intent == "general"
        assert result.method == "disabled"

    def test_empty_text_abstains(self, classifier):
        assert classifier.classify("", _vec(1, 0, 0, 0)).abstained is True


class TestTextSelection:
    def test_latest_turn_dominates(self):
        msgs = [
            Message(role="user", content="a" * 5000),
            Message(role="user", content="the latest question"),
        ]
        text = select_classification_text(msgs, history_decay=0.2, max_chars=1000)
        assert text.endswith("the latest question")
        # History is capped well below the latest turn's share of the budget.
        assert len(text) <= 1000

    def test_system_prompts_excluded(self):
        msgs = [
            Message(role="system", content="you are a helpful assistant"),
            Message(role="user", content="hello"),
        ]
        assert "helpful assistant" not in select_classification_text(msgs)

    def test_single_turn_returned_whole(self):
        msgs = [Message(role="user", content="just this")]
        assert select_classification_text(msgs) == "just this"

    def test_no_user_turns(self):
        msgs = [Message(role="system", content="nothing to see")]
        assert select_classification_text(msgs) == ""

    def test_history_included_at_reduced_weight(self):
        msgs = [
            Message(role="user", content="earlier context"),
            Message(role="user", content="current ask"),
        ]
        text = select_classification_text(msgs, history_decay=0.5)
        assert "earlier context" in text
        assert "current ask" in text


class TestBackCompat:
    def test_classify_intent_helper(self):
        assert classify_intent("Refactor this Python function") == "code"
        assert classify_intent("") == "general"

    def test_result_attributes_shape(self):
        attrs = IntentResult("code", 0.9, 0.2, "knn").as_attributes()
        assert attrs["intent"] == "code"
        assert attrs["intent_confidence"] == 0.9
        assert attrs["intent_method"] == "knn"
