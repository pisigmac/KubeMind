import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import respx

from router.providers.ollama import OllamaProvider
from router.providers.openai_compat import OpenAICompatibleProvider
from router.providers.base import CircuitState
from router.providers.registry import ProviderRegistry

class TestCredentialModeProduction:
    @pytest.mark.asyncio
    async def test_production_refuses_direct_mode(self, monkeypatch, tmp_path):
        cfg = tmp_path / "gateway.yaml"
        cfg.write_text("credential_mode: direct\nproviders: {}\n")
        monkeypatch.setenv("KUBEMIND_DEPLOYMENT", "production")
        monkeypatch.setenv("KUBEMIND_ROUTER_CONFIG", str(cfg))
        monkeypatch.delenv("KUBEMIND_CREDENTIAL_MODE", raising=False)
        with pytest.raises(ValueError, match="direct credential mode"):
            await ProviderRegistry().load_providers()

    @pytest.mark.asyncio
    async def test_production_accepts_keymint_mode(self, monkeypatch, tmp_path):
        cfg = tmp_path / "gateway.yaml"
        cfg.write_text("credential_mode: keymint\nproviders: {}\n")
        monkeypatch.setenv("KUBEMIND_DEPLOYMENT", "production")
        monkeypatch.setenv("KUBEMIND_ROUTER_CONFIG", str(cfg))
        monkeypatch.delenv("KUBEMIND_CREDENTIAL_MODE", raising=False)
        registry = ProviderRegistry()
        await registry.load_providers()
        assert registry.credential_mode == "keymint"


class TestOllamaProvider:
    @pytest.fixture
    def provider(self):
        return OllamaProvider("ollama", {
            "base_url": "http://localhost:11434",
            "models": ["llama3.1", "mistral"],
            "priority": 1,
            "free": True,
            "timeout_seconds": 60,
        })

    @pytest.mark.asyncio
    async def test_health_check_success(self, provider):
        with respx.mock:
            route = respx.get("http://localhost:11434/api/tags").mock(return_value=httpx.Response(200, json={"models": []}))
            result = await provider.health_check()
            assert result is True
            assert provider.circuit_state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_health_check_failure(self, provider):
        with respx.mock:
            respx.get("http://localhost:11434/api/tags").mock(return_value=httpx.Response(500))
            result = await provider.health_check()
            assert result is False
            assert provider.failure_count == 1

    @pytest.mark.asyncio
    async def test_chat_success(self, provider):
        from router.models import ChatRequest, Message
        req = ChatRequest(model="llama3.1", messages=[Message(role="user", content="hi")])

        with respx.mock:
            respx.post("http://localhost:11434/api/chat").mock(return_value=httpx.Response(200, json={
                "message": {"role": "assistant", "content": "Hello!"},
                "prompt_eval_count": 5,
                "eval_count": 3,
            }))
            result = await provider.chat(req)
            assert result["choices"][0]["message"]["content"] == "Hello!"
            assert result["usage"]["total_tokens"] == 8
            assert provider.circuit_state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_chat_circuit_breaker(self, provider):
        from router.models import ChatRequest, Message
        req = ChatRequest(model="llama3.1", messages=[Message(role="user", content="hi")])

        # Trip circuit breaker
        provider.circuit_state = CircuitState.OPEN
        provider.last_failure_time = __import__("time").time()

        with pytest.raises(Exception, match="Circuit breaker OPEN"):
            await provider.chat(req)

    @pytest.mark.asyncio
    async def test_embeddings_success(self, provider):
        from router.models import EmbeddingsRequest
        req = EmbeddingsRequest(model="nomic-embed-text", input="hello world")

        with respx.mock:
            respx.post("http://localhost:11434/api/embeddings").mock(return_value=httpx.Response(200, json={
                "embedding": [0.1, 0.2, 0.3],
            }))
            result = await provider.embeddings(req)
            assert result["data"][0]["embedding"] == [0.1, 0.2, 0.3]


class TestOpenAICompatibleProvider:
    @pytest.fixture
    def provider(self):
        return OpenAICompatibleProvider("openai", {
            "base_url": "https://api.openai.com/v1",
            "api_key": "test-key",
            "models": ["gpt-4o-mini"],
            "priority": 5,
            "free": False,
            "timeout_seconds": 30,
        })

    @pytest.mark.asyncio
    async def test_chat_success(self, provider):
        from router.models import ChatRequest, Message
        req = ChatRequest(model="gpt-4o-mini", messages=[Message(role="user", content="hi")])

        with respx.mock:
            respx.post("https://api.openai.com/v1/chat/completions").mock(return_value=httpx.Response(200, json={
                "id": "test-id",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "gpt-4o-mini",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello!"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            }))
            result = await provider.chat(req)
            assert result["choices"][0]["message"]["content"] == "Hello!"

    @pytest.mark.asyncio
    async def test_health_check(self, provider):
        with respx.mock:
            respx.get("https://api.openai.com/v1/models").mock(return_value=httpx.Response(200, json={"data": []}))
            result = await provider.health_check()
            assert result is True
