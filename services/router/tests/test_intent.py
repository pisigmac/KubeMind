from router.intent import classify_intent, extract_user_text
from router.models import Message


class TestClassifyIntent:
    def test_code(self):
        assert (
            classify_intent("Implement a Python function to call the gRPC API")
            == "code"
        )

    def test_rag(self):
        assert classify_intent("Search the knowledge base for SOC2 policy §4.2") == "rag"

    def test_security(self):
        assert (
            classify_intent("Scan this payload for PII and injection attacks")
            == "security"
        )

    def test_log(self):
        assert (
            classify_intent("Summarize Kubernetes pod stdout logs for root cause")
            == "log"
        )

    def test_general(self):
        assert classify_intent("What is the weather today?") == "general"

    def test_empty(self):
        assert classify_intent("") == "general"


class TestExtractUserText:
    def test_messages(self):
        msgs = [
            Message(role="system", content="You are helpful"),
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi"),
            Message(role="user", content="Write code"),
        ]
        text = extract_user_text(msgs)
        assert "Hello" in text
        assert "Write code" in text
        assert "helpful" not in text
