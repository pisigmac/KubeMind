"""End-to-end dispatch pipeline.

Exercises the full ordering -- exact cache, sensitivity, embed, classify,
semantic cache, retrieval, route, decision record -- against fake providers so
no network or model is required.
"""

import json
import pytest

from fastapi.testclient import TestClient

from router import main as m
from router import metrics as router_metrics
from router.auth import Authenticator
from router.cache import SemanticCache
from router.intent import ClassifierConfig, IntentClassifier
from router.policy import PolicyEngine
from router.profiles import ProfileRegistry
from router.providers.registry import ProviderRegistry
from tests.test_routing import FakeProvider

PRIVATE_KEY = (
    "-----BEGIN PRIVATE KEY-----\nMIIBVgIBADANBgkqhkiG9w0\n-----END PRIVATE KEY-----"
)

CONFIG = {
    "routing": {
        "default_profile": "general",
        "profiles": {
            "general": {"pool": ["ollama", "groq"]},
            "code": {"pool": ["deepseek_local", "ollama"], "temperature": 0.2},
            "knowledge": {"pool": ["ollama"], "retrieval": True, "retrieval_top_k": 2},
        },
        "intents": {
            "code": {"profile": "code"},
            "rag": {"profile": "knowledge"},
        },
    },
    "policy": {
        "enabled": True,
        "fail_closed": True,
        "default": {
            "rules": [
                {"detector": "private_key", "action": "block"},
                {"detector": "any_pii", "action": "local_only"},
            ]
        },
    },
}


class StubCache:
    """In-memory stand-in for the exact Redis cache."""

    def __init__(self):
        self.store = {}
        self.is_connected = True
        self.client = None

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ttl=300):
        self.store[key] = json.loads(json.dumps(value))

    async def clear(self):
        self.store.clear()

    async def stats(self):
        return {"connected": True, "keys_in_db": len(self.store)}


class StubSemanticCache(SemanticCache):
    """Deterministic embeddings keyed off the prompt text."""

    def __init__(self, vectors=None):
        super().__init__(redis_client=None, enabled=True)
        self.vectors = vectors or {}
        self.entries = []
        self.embed_calls = 0

    async def embed(self, text):
        self.embed_calls += 1
        return self.vectors.get(text, [1.0, 0.0, 0.0])

    async def lookup(self, workspace_id, embedding, **kwargs):
        sig = kwargs.get("sig")
        for entry in self.entries:
            if sig is not None and entry.get("signature") not in (None, sig):
                continue
            if entry["embedding"] == embedding:
                return entry["response"], 0.0, {"intent": entry.get("intent")}
        return None

    async def store(self, workspace_id, embedding, response, **kwargs):
        self.entries.append(
            {
                "embedding": embedding,
                "response": response,
                "intent": kwargs.get("intent"),
                "signature": kwargs.get("sig"),
                "partition": kwargs.get("partition"),
            }
        )


@pytest.fixture(autouse=True)
def wire(monkeypatch):
    """Install the fake stack into the module-level globals main.py uses."""
    router_metrics.reset()

    registry = ProviderRegistry()
    registry.config = CONFIG
    registry.providers = {
        "ollama": FakeProvider(
            "ollama", {"local": True, "priority": 1, "free": True}
        ),
        "deepseek_local": FakeProvider(
            "deepseek_local", {"local": True, "priority": 2, "free": True}
        ),
        "groq": FakeProvider("groq", {"priority": 3, "free": True}),
    }

    classifier = IntentClassifier(
        config=ClassifierConfig(
            knn_k=1, margin_threshold=0.05, min_similarity=0.5, temperature=0.1,
            rule_prior_weight=0.0,
        )
    )
    classifier.index = {
        "code": [[1.0, 0.0, 0.0]],
        "rag": [[0.0, 1.0, 0.0]],
    }
    classifier.examples = {"code": [], "rag": []}
    classifier.is_ready = True

    monkeypatch.setattr(m, "registry", registry)
    monkeypatch.setattr(m, "cache", StubCache())
    monkeypatch.setattr(m, "semantic_cache", StubSemanticCache())
    monkeypatch.setattr(m, "rate_limiter", None)
    monkeypatch.setattr(m, "usage_tracker", None)
    monkeypatch.setattr(m, "sentinel_client", None)
    monkeypatch.setattr(m, "mind_client", None)
    monkeypatch.setattr(m, "classifier", classifier)
    monkeypatch.setattr(m, "policy_engine", PolicyEngine.from_config(CONFIG))
    monkeypatch.setattr(m, "profiles", ProfileRegistry.from_config(CONFIG))
    monkeypatch.setattr(m, "authenticator", Authenticator())
    monkeypatch.setattr(m, "feedback_log", None)
    from router.cascade import CascadeConfig

    monkeypatch.setattr(m, "cascade_config", CascadeConfig(enabled=False))
    return m


@pytest.fixture
def client():
    return TestClient(m.app)


def chat(client, prompt, **kwargs):
    body = {
        "model": "llama3.1",
        "messages": [{"role": "user", "content": prompt}],
    }
    body.update(kwargs)
    return client.post("/v1/chat/completions", json=body)


class TestIntentRouting:
    def test_code_prompt_routes_to_code_profile(self, client):
        m.semantic_cache.vectors = {"write a function": [1.0, 0.0, 0.0]}
        r = chat(client, "write a function")
        assert r.status_code == 200
        body = r.json()
        assert body["intent"] == "code"
        assert body["profile"] == "code"
        # code profile pool puts deepseek_local first
        assert body["provider"] == "deepseek_local"

    def test_ambiguous_prompt_abstains_to_general(self, client):
        m.semantic_cache.vectors = {"hmm": [1.0, 1.0, 0.0]}
        body = chat(client, "hmm").json()
        assert body["intent"] == "general"
        assert body["profile"] == "general"
        assert body["provider"] == "ollama"
        assert body["routing_decision"]["reason_code"] == (
            "CLASSIFIER_LOW_CONFIDENCE_FALLBACK"
        )

    def test_classifier_failure_falls_back_with_stable_reason(self, client, monkeypatch):
        monkeypatch.setattr(
            m.classifier,
            "classify",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("private")),
        )

        response = chat(client, "ordinary request")

        assert response.status_code == 200
        body = response.json()
        assert body["intent"] == "general"
        assert body["routing_decision"]["reason_code"] == "CLASSIFIER_FAILURE_FALLBACK"
        assert "private" not in response.text

    def test_response_carries_decision_metadata(self, client):
        body = chat(client, "write a function").json()
        for field in (
            "intent",
            "intent_confidence",
            "profile",
            "policy_action",
            "egress_class",
            "route_target",
        ):
            assert field in body


class TestCacheOrdering:
    def test_exact_hit_still_evaluates_current_policy_and_profile(self, client):
        m.semantic_cache.vectors = {"repeat me": [1.0, 0.0, 0.0]}
        first = chat(client, "repeat me").json()
        assert first["cache_hit"] is False
        embeds_after_first = m.semantic_cache.embed_calls

        second = chat(client, "repeat me").json()
        assert second["cache_hit"] is True
        assert second["cache_type"] == "exact"
        # Policy/profile resolution precedes cache reads to prevent stale or
        # cross-policy responses. Classification may therefore embed again.
        assert m.semantic_cache.embed_calls > embeds_after_first

    def test_exact_hit_reports_stored_intent(self, client):
        m.semantic_cache.vectors = {"write a function": [1.0, 0.0, 0.0]}
        chat(client, "write a function")
        cached = chat(client, "write a function").json()
        assert cached["cache_type"] == "exact"
        # Without persisting intent this would be a guess, since an exact hit
        # never computes an embedding.
        assert cached["intent"] == "code"

    def test_semantic_hit_when_exact_misses(self, client):
        m.semantic_cache.vectors = {
            "first phrasing": [0.5, 0.5, 0.5],
            "second phrasing": [0.5, 0.5, 0.5],
        }
        chat(client, "first phrasing")
        second = chat(client, "second phrasing").json()
        assert second["cache_hit"] is True
        assert second["cache_type"] == "semantic"

    def test_signature_prevents_cross_model_reuse(self, client):
        m.semantic_cache.vectors = {"same text": [0.3, 0.3, 0.3]}
        chat(client, "same text", model="llama3.1")
        other = chat(client, "same text", model="mistral").json()
        # Same vector, different model: must not serve the cached answer.
        assert other["cache_hit"] is False

    def test_bypass_header_skips_cache(self, client):
        chat(client, "repeat me")
        r = client.post(
            "/v1/chat/completions",
            json={"model": "llama3.1", "messages": [{"role": "user", "content": "repeat me"}]},
            headers={"X-KubeMind-Cache": "bypass"},
        )
        assert r.json()["cache_hit"] is False

    def test_exact_cache_key_is_workspace_and_policy_scoped(self):
        req = m.ChatRequest(
            model="llama3.1",
            messages=[m.Message(role="user", content="same")],
        )
        profile = m.RouteProfile("general")
        policy = {"action": "allow", "rules": []}
        first = m._exact_cache_key("chat", "workspace-a", req, profile, policy)
        assert first != m._exact_cache_key("chat", "workspace-b", req, profile, policy)
        assert first != m._exact_cache_key(
            "chat", "workspace-a", req, profile, {"action": "local_only", "rules": []}
        )

    def test_tools_are_not_cached(self, client):
        kwargs = {"tools": [{"type": "function", "function": {"name": "lookup"}}]}
        first = chat(client, "repeat me", **kwargs).json()
        second = chat(client, "repeat me", **kwargs).json()
        assert first["cache_hit"] is False
        assert second["cache_hit"] is False


class TestPolicyEnforcement:
    def test_secret_is_blocked_before_dispatch(self, client):
        r = chat(client, f"deploy this key {PRIVATE_KEY}")
        assert r.status_code == 403
        assert r.json()["detail"]["error"] == "blocked_by_policy"
        # Nothing reached a provider.
        assert all(p.calls == 0 for p in m.registry.providers.values())

    def test_pii_forces_local_provider(self, client):
        m.semantic_cache.vectors = {"contact bob@example.com": [0.0, 0.0, 1.0]}
        body = chat(client, "contact bob@example.com").json()
        assert body["policy_action"] == "local_only"
        assert body["egress_class"] == "local_only"
        assert m.registry.is_local(body["provider"])

    def test_local_only_refuses_rather_than_leaking(self, client):
        from router.providers.base import CircuitState

        for name in ("ollama", "deepseek_local"):
            m.registry.providers[name].circuit_state = CircuitState.OPEN
            m.registry.providers[name].last_failure_time = 9e18
        r = chat(client, "contact bob@example.com")
        assert r.status_code == 503
        assert m.registry.providers["groq"].calls == 0

    def test_sensitive_prompt_is_not_cached(self, client):
        chat(client, "contact bob@example.com")
        second = chat(client, "contact bob@example.com").json()
        assert second["cache_hit"] is False

    def test_policy_runs_before_classification(self, client):
        """A blocked prompt must not depend on the classifier having an opinion."""
        m.classifier.is_ready = False
        r = chat(client, f"here {PRIVATE_KEY}")
        assert r.status_code == 403


class TestFallback:
    def test_failure_walks_the_chain(self, client):
        m.semantic_cache.vectors = {"write a function": [1.0, 0.0, 0.0]}
        m.registry.providers["deepseek_local"].should_fail = True
        body = chat(client, "write a function").json()
        assert body["provider"] == "ollama"
        assert body["fallback"] is True

    def test_all_providers_failing_returns_502(self, client):
        for p in m.registry.providers.values():
            p.should_fail = True
        response = chat(client, "anything")
        assert response.status_code == 502
        assert response.json()["detail"] == "Provider unavailable"
        assert "anything" not in response.text


class TestStreaming:
    def test_stream_returns_sse_chunks(self, client):
        r = chat(client, "hello", stream=True)
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
        assert "data: " in r.text
        assert "[DONE]" in r.text



class TestRetrieval:
    def test_retrieval_intent_augments_from_mind(self, client, monkeypatch):
        from router.mind_client import RetrievalOutcome, STATUS_USED

        class StubMind:
            enabled = True

            async def retrieve(self, q, ws, top_k=4):
                return RetrievalOutcome(
                    STATUS_USED,
                    hits=[{"content": "Expenses are reimbursed monthly.", "source": "handbook"}],
                    context="CONTEXT: Expenses are reimbursed monthly.",
                )

        monkeypatch.setattr(m, "mind_client", StubMind())
        m.semantic_cache.vectors = {"what does the handbook say": [0.0, 1.0, 0.0]}
        body = chat(client, "what does the handbook say").json()
        assert body["intent"] == "rag"
        assert body["retrieval_used"] is True
        assert body["retrieval_status"] == "used"
        assert body["routing_decision"]["retrieval_status"] == "used"

        sent = m.registry.providers["ollama"].last_request
        assert any("CONTEXT:" in msg.content for msg in sent.messages)

    def test_empty_corpus_is_labelled_not_pretended(self, client, monkeypatch):
        from router.mind_client import RetrievalOutcome, STATUS_EMPTY

        class EmptyMind:
            enabled = True

            async def retrieve(self, q, ws, top_k=4):
                return RetrievalOutcome(STATUS_EMPTY)

        monkeypatch.setattr(m, "mind_client", EmptyMind())
        m.semantic_cache.vectors = {"what does the handbook say": [0.0, 1.0, 0.0]}
        body = chat(client, "what does the handbook say").json()
        assert body["intent"] == "rag"
        assert body["retrieval_used"] is False
        assert body["retrieval_status"] == "empty"

    def test_local_retrieval_outage_is_labelled(self, client, monkeypatch):
        from router.mind_client import RetrievalOutcome, STATUS_UNAVAILABLE

        class BrokenMind:
            enabled = True

            async def retrieve(self, q, ws, top_k=4):
                return RetrievalOutcome(STATUS_UNAVAILABLE)

        monkeypatch.setattr(m, "mind_client", BrokenMind())
        monkeypatch.delenv("KUBEMIND_DEPLOYMENT", raising=False)
        m.semantic_cache.vectors = {"what does the handbook say": [0.0, 1.0, 0.0]}
        body = chat(client, "what does the handbook say").json()
        assert body["retrieval_used"] is False
        assert body["retrieval_status"] == "unavailable"
        assert body["intent"] == "rag"

    def test_production_retrieval_outage_fails_closed(self, client, monkeypatch):
        from router.mind_client import RetrievalOutcome, STATUS_UNAVAILABLE

        class BrokenMind:
            enabled = True

            async def retrieve(self, q, ws, top_k=4):
                return RetrievalOutcome(STATUS_UNAVAILABLE)

        monkeypatch.setattr(m, "mind_client", BrokenMind())
        monkeypatch.setenv("KUBEMIND_DEPLOYMENT", "production")
        m.semantic_cache.vectors = {"what does the handbook say": [0.0, 1.0, 0.0]}
        response = chat(client, "what does the handbook say")
        assert response.status_code == 503
        assert "retrieval" in response.json()["detail"].lower()


class TestObservability:
    def test_routing_report_counts_cache_hits_as_free(self, client):
        m.semantic_cache.vectors = {"write a function": [1.0, 0.0, 0.0]}
        chat(client, "write a function")
        chat(client, "write a function")

        report = client.get("/v1/routing/report").json()
        code = report["intents"]["code"]
        assert code["requests"] == 2
        assert code["cache_hits"] == 1
        # One completion was actually paid for, not two.
        assert code["billable_requests"] == 1

    def test_prometheus_endpoint_renders(self, client):
        chat(client, "write a function")
        body = client.get("/metrics").text
        assert "kubemind_router_intent_requests_total" in body
        assert "kubemind_router_policy_actions_total" in body

    def test_classify_endpoint_is_a_dry_run(self, client):
        m.semantic_cache.vectors = {"write a function": [1.0, 0.0, 0.0]}
        body = client.post("/v1/classify", json={"prompt": "write a function"}).json()
        assert body["intent"] == "code"
        assert body["profile"] == "code"
        assert "policy_action" in body
        # No provider was called.
        assert all(p.calls == 0 for p in m.registry.providers.values())

    def test_intents_endpoint_lists_wiring(self, client):
        body = client.get("/v1/intents").json()
        names = {i["name"] for i in body["intents"]}
        assert {"code", "rag"} <= names


class TestAuth:
    def test_open_mode_trusts_header(self, client):
        r = client.post(
            "/v1/chat/completions",
            json={"model": "llama3.1", "messages": [{"role": "user", "content": "hi"}]},
            headers={"X-Workspace-ID": "team-a"},
        )
        assert r.status_code == 200

    def test_key_binds_workspace(self, client, monkeypatch):
        monkeypatch.setattr(m, "authenticator", Authenticator({"secret-key": "acme"}))
        r = client.post(
            "/v1/chat/completions",
            json={"model": "llama3.1", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 401

        r = client.post(
            "/v1/chat/completions",
            json={"model": "llama3.1", "messages": [{"role": "user", "content": "hi"}]},
            headers={"X-API-Key": "secret-key"},
        )
        assert r.status_code == 200

    def test_header_cannot_redirect_to_another_workspace(self, client, monkeypatch):
        monkeypatch.setattr(m, "authenticator", Authenticator({"secret-key": "acme"}))
        r = client.post(
            "/v1/chat/completions",
            json={"model": "llama3.1", "messages": [{"role": "user", "content": "hi"}]},
            headers={"X-API-Key": "secret-key", "X-Workspace-ID": "victim"},
        )
        assert r.status_code == 403

    def test_cache_clear_requires_admin(self, client):
        assert client.post("/v1/cache/clear").status_code == 403


class TestRestoreResponseToolCalls:
    """Verify pseudonymized tokens in tool_calls and function_call are restored."""

    def test_restore_tokens_in_tool_call_arguments(self):
        token_map = {"[KM_PERSON_1]": "Alice Smith", "[KM_EMAIL_1]": "alice@example.com"}
        response = {
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_abc",
                                "type": "function",
                                "function": {
                                    "name": "lookup_user",
                                    "arguments": '{"name": "[KM_PERSON_1]", "email": "[KM_EMAIL_1]"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }
        from router.main import _restore_response
        result = _restore_response(response, token_map)
        args = result["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
        assert "[KM_PERSON_1]" not in args
        assert "Alice Smith" in args
        assert "alice@example.com" in args

    def test_restore_tokens_in_legacy_function_call(self):
        token_map = {"[KM_PERSON_1]": "Bob Jones"}
        response = {
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "function_call": {
                            "name": "greet",
                            "arguments": '{"user": "[KM_PERSON_1]"}',
                        },
                    },
                }
            ]
        }
        from router.main import _restore_response
        result = _restore_response(response, token_map)
        args = result["choices"][0]["message"]["function_call"]["arguments"]
        assert "Bob Jones" in args
        assert "[KM_PERSON_1]" not in args

    def test_restore_handles_multiple_tool_calls(self):
        token_map = {"[KM_PERSON_1]": "Alice", "[KM_PERSON_2]": "Bob"}
        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {"id": "c1", "type": "function", "function": {"name": "f1", "arguments": '{"x": "[KM_PERSON_1]"}'}},
                            {"id": "c2", "type": "function", "function": {"name": "f2", "arguments": '{"y": "[KM_PERSON_2]"}'}},
                        ],
                    }
                }
            ]
        }
        from router.main import _restore_response
        result = _restore_response(response, token_map)
        assert "Alice" in result["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
        assert "Bob" in result["choices"][0]["message"]["tool_calls"][1]["function"]["arguments"]

    def test_restore_no_regression_on_content(self):
        token_map = {"[KM_PERSON_1]": "Alice"}
        response = {
            "choices": [{"message": {"role": "assistant", "content": "Hello [KM_PERSON_1]"}}]
        }
        from router.main import _restore_response
        result = _restore_response(response, token_map)
        assert result["choices"][0]["message"]["content"] == "Hello Alice"

