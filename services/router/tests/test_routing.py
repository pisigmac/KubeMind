"""Provider selection, egress constraints and fallback chains."""

import pytest
import yaml

from router.providers.base import BaseProvider, CircuitState
from router.providers.registry import ProviderRegistry
from router.providers.keymint_managed import KeyMintManagedProvider
from router.profiles import ProfileRegistry, RouteProfile


class FakeProvider(BaseProvider):
    def __init__(self, name, config):
        super().__init__(name, config)
        self.calls = 0
        self.should_fail = False
        self.last_request = None

    async def chat(self, request):
        self.calls += 1
        self.last_request = request
        if self.should_fail:
            raise RuntimeError(f"{self.name} unavailable")
        return {
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "model": request.model,
        }

    async def embeddings(self, request):
        return {"data": [], "usage": {}}

    async def health_check(self):
        return True


@pytest.fixture
def registry():
    r = ProviderRegistry()
    r.config = {
        "routing": {"target_aliases": {"local": "ollama", "deepseek-r1": "deepseek_local"}}
    }
    r.providers = {
        "ollama": FakeProvider(
            "ollama",
            {"local": True, "priority": 1, "free": True, "models": ["llama3.1", "mistral"]},
        ),
        "deepseek_local": FakeProvider(
            "deepseek_local",
            {"local": True, "priority": 2, "free": True, "models": ["deepseek-r1"]},
        ),
        # No declared model list: the opt-out for a local server that serves
        # whatever has been loaded into it.
        "vllm": FakeProvider("vllm", {"local": True, "priority": 4, "free": True}),
        "groq": FakeProvider(
            "groq", {"priority": 3, "free": True, "models": ["llama-3.1-70b"]}
        ),
        "openai": FakeProvider(
            "openai", {"priority": 6, "free": False, "models": ["gpt-4o", "gpt-4o-mini"]}
        ),
    }
    return r


LOCAL_NAMES = ("ollama", "deepseek_local", "vllm")


def _open_circuit(registry, *names):
    for name in names:
        registry.providers[name].circuit_state = CircuitState.OPEN
        registry.providers[name].last_failure_time = 9e18


class TestModelSupport:
    def test_remote_provider_rejects_unknown_model(self, registry):
        assert registry.supports_model("groq", "gpt-4o") is False
        assert registry.supports_model("groq", "llama-3.1-70b") is True

    def test_declared_list_is_binding_even_for_local(self, registry):
        # Otherwise a request for gpt-4o selects Ollama and fails at dispatch.
        assert registry.supports_model("ollama", "gpt-4o") is False

    def test_local_provider_without_a_list_accepts_anything(self, registry):
        assert registry.supports_model("vllm", "some-new-model") is True

    def test_preferred_provider_must_support_the_model(self, registry):
        """The bug this fixes: a preferred target used to bypass the filter."""
        assert registry.provider_by_name("groq", model="gpt-4o") is None
        assert registry.provider_by_name("groq", model="llama-3.1-70b") is not None

    def test_select_provider_does_not_honour_impossible_preference(self, registry):
        chosen = registry.select_provider("gpt-4o", preferred_provider="groq")
        assert chosen is not None
        assert chosen.name != "groq"
        assert registry.supports_model(chosen.name, "gpt-4o")

    def test_alias_resolution(self, registry):
        assert registry.provider_by_name("local", model="llama3.1").name == "ollama"


class TestKeyMintManagedProviders:
    @pytest.mark.asyncio
    async def test_remote_metadata_is_not_directly_executable(self, tmp_path, monkeypatch):
        config_path = tmp_path / "gateway.yaml"
        config_path.write_text(
            yaml.safe_dump(
                {
                    "credential_mode": "keymint",
                    "providers": {
                        "openai": {
                            "models": ["gpt-4o-mini"],
                        }
                    }
                }
            )
        )
        monkeypatch.setenv("KUBEMIND_ROUTER_CONFIG", str(config_path))
        registry = ProviderRegistry()

        await registry.load_providers()

        provider = registry.providers["openai"]
        assert isinstance(provider, KeyMintManagedProvider)
        assert "api_key" not in provider.config
        assert registry.eligible_providers("gpt-4o-mini") == []
        assert registry.eligible_providers(
            "gpt-4o-mini", keymint_managed=True
        ) == [provider]
        with pytest.raises(RuntimeError, match="KEYMINT_CAPABILITY_REQUIRED"):
            await provider.chat(None)

    @pytest.mark.asyncio
    async def test_keymint_mode_rejects_ambient_api_key(self, tmp_path, monkeypatch):
        config_path = tmp_path / "gateway.yaml"
        config_path.write_text(
            yaml.safe_dump(
                {
                    "credential_mode": "keymint",
                    "providers": {
                        "openai": {
                            "api_key": "${OPENAI_API_KEY}",
                            "models": ["gpt-4o-mini"],
                        }
                    }
                }
            )
        )
        monkeypatch.setenv("KUBEMIND_ROUTER_CONFIG", str(config_path))
        monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret")

        with pytest.raises(ValueError, match="ambient api_key configuration is forbidden"):
            await ProviderRegistry().load_providers()

    @pytest.mark.asyncio
    async def test_direct_mode_loads_explicit_provider_key(self, tmp_path, monkeypatch):
        config_path = tmp_path / "gateway.yaml"
        config_path.write_text(
            yaml.safe_dump(
                {
                    "credential_mode": "direct",
                    "providers": {
                        "openai": {
                            "api_key": "${OPENAI_API_KEY}",
                            "base_url": "https://api.openai.com/v1",
                            "models": ["gpt-4o-mini"],
                        }
                    },
                }
            )
        )
        monkeypatch.setenv("KUBEMIND_ROUTER_CONFIG", str(config_path))
        monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret")

        registry = ProviderRegistry()
        await registry.load_providers()

        assert registry.credential_mode == "direct"
        assert registry.select_provider("gpt-4o-mini") is not None
        await registry.close()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mode", [None, "automatic", ""])
    async def test_missing_or_invalid_mode_fails_startup(
        self, tmp_path, monkeypatch, mode
    ):
        config_path = tmp_path / "gateway.yaml"
        config = {"providers": {}}
        if mode is not None:
            config["credential_mode"] = mode
        config_path.write_text(yaml.safe_dump(config))
        monkeypatch.setenv("KUBEMIND_ROUTER_CONFIG", str(config_path))

        with pytest.raises(ValueError, match="credential_mode must be explicitly"):
            await ProviderRegistry().load_providers()


class TestCostOrdering:
    def test_free_before_paid(self, registry):
        # vllm declares no model list so it competes with paid openai here.
        eligible = registry.eligible_providers("gpt-4o")
        assert [p.name for p in eligible] == ["vllm", "openai"]

    def test_priority_orders_within_free_tier(self, registry):
        eligible = registry.eligible_providers("llama3.1")
        assert [p.name for p in eligible] == ["ollama", "vllm"]

    def test_unhealthy_provider_excluded(self, registry):
        _open_circuit(registry, "ollama")
        names = [p.name for p in registry.eligible_providers("llama3.1")]
        assert "ollama" not in names


class TestPoolConstraints:
    def test_pool_restricts_candidates(self, registry):
        eligible = registry.eligible_providers("deepseek-r1", pool=["deepseek_local"])
        assert [p.name for p in eligible] == ["deepseek_local"]

    def test_pool_aliases_resolved(self, registry):
        eligible = registry.eligible_providers("llama3.1", pool=["local"])
        assert [p.name for p in eligible] == ["ollama"]

    def test_unsatisfiable_pool_falls_back(self, registry):
        # A profile naming a provider that is down should still get served.
        chosen = registry.select_provider("gpt-4o", pool=["deepseek_local", "groq"])
        assert chosen is not None


class TestEgressConstraint:
    def test_local_only_excludes_remote(self, registry):
        eligible = registry.eligible_providers("llama3.1", local_only=True)
        names = [p.name for p in eligible]
        assert names and all(registry.is_local(n) for n in names)
        assert "groq" not in names and "openai" not in names

    def test_local_only_never_falls_back_to_cloud(self, registry):
        """An egress constraint must fail closed, unlike a pool constraint."""
        _open_circuit(registry, *LOCAL_NAMES)
        assert registry.build_route_chain("llama3.1", local_only=True) == []
        assert registry.select_provider("llama3.1", local_only=True) is None

    def test_local_only_ignores_remote_preference(self, registry):
        chain = registry.build_route_chain(
            "llama3.1", preferred_provider="openai", local_only=True
        )
        assert all(registry.is_local(p.name) for p in chain)


class TestRouteChain:
    def test_chain_is_ordered_and_deduplicated(self, registry):
        chain = registry.build_route_chain(
            "deepseek-r1", preferred_provider="deepseek_local"
        )
        names = [p.name for p in chain]
        assert names[0] == "deepseek_local"
        assert len(names) == len(set(names))

    def test_chain_honours_explicit_fallback(self, registry):
        chain = registry.build_route_chain(
            "llama3.1", pool=["ollama"], fallback_provider="vllm"
        )
        assert [p.name for p in chain] == ["ollama", "vllm"]

    def test_chain_drops_a_fallback_that_cannot_serve_the_model(self, registry):
        chain = registry.build_route_chain(
            "llama3.1", pool=["ollama"], fallback_provider="deepseek_local"
        )
        assert [p.name for p in chain] == ["ollama"]

    def test_chain_capped(self, registry):
        chain = registry.build_route_chain("llama3.1", max_attempts=2)
        assert len(chain) <= 2

    @pytest.mark.asyncio
    async def test_route_with_fallback_respects_preference(self, registry):
        """Previously this ignored its arguments and returned the primary."""
        provider, used_fallback = await registry.route_with_fallback(
            "deepseek-r1", preferred_provider="deepseek_local"
        )
        assert provider.name == "deepseek_local"
        assert used_fallback is False

    @pytest.mark.asyncio
    async def test_route_with_fallback_flags_substitution(self, registry):
        provider, used_fallback = await registry.route_with_fallback(
            "gpt-4o", preferred_provider="groq"
        )
        assert provider.name != "groq"
        assert used_fallback is True

    def test_select_fallback_excludes_failed(self, registry):
        fb = registry.select_fallback("ollama", "llama3.1")
        assert fb is not None and fb.name != "ollama"


class TestProfiles:
    def test_intent_maps_to_profile(self):
        reg = ProfileRegistry.from_config(
            {
                "routing": {
                    "profiles": {"fast": {"pool": ["ollama"], "temperature": 0.1}},
                    "intents": {"log": {"profile": "fast"}},
                }
            }
        )
        profile = reg.for_intent("log")
        assert profile.name == "fast"
        assert profile.pool == ["ollama"]
        assert profile.temperature == 0.1

    def test_unknown_intent_gets_default(self):
        reg = ProfileRegistry.from_config({"routing": {}})
        assert reg.for_intent("nonexistent").name == "default"

    def test_legacy_prefer_targets_still_work(self):
        reg = ProfileRegistry.from_config(
            {"routing": {"prefer_targets": {"code": "deepseek_local"}}}
        )
        assert reg.for_intent("code").pool == ["deepseek_local"]

    def test_profile_carries_cache_policy(self):
        reg = ProfileRegistry.from_config(
            {
                "routing": {
                    "profiles": {
                        "secure": {"cache": {"enabled": False}},
                        "tight": {"cache": {"distance_threshold": 0.01}},
                    },
                    "intents": {
                        "security": {"profile": "secure"},
                        "code": {"profile": "tight"},
                    },
                }
            }
        )
        assert reg.for_intent("security").cache.enabled is False
        assert reg.for_intent("code").cache.distance_threshold == 0.01

    def test_retrieval_flag(self):
        reg = ProfileRegistry.from_config(
            {
                "routing": {
                    "profiles": {"kb": {"retrieval": True, "retrieval_top_k": 7}},
                    "intents": {"rag": {"profile": "kb"}},
                }
            }
        )
        assert reg.for_intent("rag").retrieval is True
        assert reg.for_intent("rag").retrieval_top_k == 7

    def test_defaults_are_conservative(self):
        p = RouteProfile.from_dict("x", {})
        assert p.pool == []
        assert p.retrieval is False
        assert p.cache.enabled is True
