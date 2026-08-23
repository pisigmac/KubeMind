"""Tests for the optional escalation cascade."""

from router.cascade import (
    CascadeConfig,
    extract_answer_text,
    reorder_for_cascade,
    should_escalate,
)


class Fake:
    def __init__(self, name):
        self.name = name


def test_disabled_never_escalates():
    d = should_escalate(
        config=CascadeConfig(enabled=False),
        confidence=0.1,
        abstained=True,
        answer_text="x",
        local_only=False,
    )
    assert d.should_escalate is False


def test_local_only_blocks_escalation():
    d = should_escalate(
        config=CascadeConfig(enabled=True, confidence_below=0.9),
        confidence=0.1,
        abstained=False,
        answer_text="short",
        local_only=True,
    )
    assert d.should_escalate is False
    assert d.reason == "local_only_blocks_escalation"


def test_low_confidence_escalates():
    d = should_escalate(
        config=CascadeConfig(enabled=True, confidence_below=0.55),
        confidence=0.2,
        abstained=False,
        answer_text="a perfectly long enough answer for the threshold",
        local_only=False,
    )
    assert d.should_escalate is True
    assert d.reason == "low_confidence"


def test_thin_answer_escalates():
    d = should_escalate(
        config=CascadeConfig(enabled=True, confidence_below=0.1, min_answer_chars=40),
        confidence=0.9,
        abstained=False,
        answer_text="ok",
        local_only=False,
    )
    assert d.should_escalate is True
    assert d.reason == "thin_answer"


def test_good_answer_stays():
    d = should_escalate(
        config=CascadeConfig(enabled=True, confidence_below=0.1, min_answer_chars=10),
        confidence=0.9,
        abstained=False,
        answer_text="a long enough answer",
        local_only=False,
    )
    assert d.should_escalate is False


def test_reorder_puts_local_first():
    chain = [Fake("groq"), Fake("ollama"), Fake("openai")]
    out = reorder_for_cascade(
        chain,
        config=CascadeConfig(enabled=True, prefer_local_first=True),
        is_local=lambda n: n == "ollama",
    )
    assert [p.name for p in out] == ["ollama", "groq", "openai"]


def test_extract_answer_text():
    assert (
        extract_answer_text(
            {"choices": [{"message": {"content": "hello"}}]}
        )
        == "hello"
    )
