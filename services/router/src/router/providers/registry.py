import os
import yaml
from typing import Dict, List, Optional, Any, Sequence

from router.providers.base import BaseProvider
from router.providers.ollama import OllamaProvider
from router.providers.openai_compat import OpenAICompatibleProvider

# Providers that do not require an API key when base_url is set
LOCAL_PROVIDER_TYPES = {"ollama", "vllm", "deepseek_local"}


class NoEligibleProvider(Exception):
    """No provider satisfies the constraints (pool, egress class, model)."""

    def __init__(self, message: str, *, local_only: bool = False):
        super().__init__(message)
        self.local_only = local_only


class ProviderRegistry:
    def __init__(self, cache=None, usage_tracker=None):
        self.providers: Dict[str, BaseProvider] = {}
        self.config: Dict[str, Any] = {}
        self.cache = cache
        self.usage_tracker = usage_tracker

    async def load_providers(self):
        config_path = os.environ.get(
            "KUBEMIND_ROUTER_CONFIG",
            os.environ.get("SWITCHBOARD_CONFIG", "config/gateway.yaml"),
        )
        with open(config_path) as f:
            raw = yaml.safe_load(f)

        self.config = raw or {}
        for name, cfg in self.config.get("providers", {}).items():
            resolved = self._resolve_env(cfg)
            is_local = bool(resolved.get("local")) or name in LOCAL_PROVIDER_TYPES

            if not is_local and not resolved.get("api_key"):
                print(f"[router] Skipping provider {name}: no API key configured")
                continue

            if is_local and not resolved.get("base_url") and name != "ollama":
                # ollama has default localhost; vllm/deepseek need explicit URL
                if name != "ollama":
                    default_env = {
                        "vllm": "VLLM_BASE_URL",
                        "deepseek_local": "DEEPSEEK_LOCAL_BASE_URL",
                    }.get(name)
                    if default_env and not os.environ.get(default_env):
                        print(f"[router] Skipping provider {name}: no base_url")
                        continue

            if name == "ollama" or (
                is_local and "ollama" in (resolved.get("base_url") or "")
            ):
                # Prefer Ollama native API when name is ollama
                if name == "ollama":
                    self.providers[name] = OllamaProvider(name, resolved)
                else:
                    # deepseek_local may point at Ollama or OpenAI-compat server
                    base = (resolved.get("base_url") or "").lower()
                    if "11434" in base or "ollama" in base:
                        self.providers[name] = OllamaProvider(name, resolved)
                    else:
                        self.providers[name] = OpenAICompatibleProvider(name, resolved)
            else:
                self.providers[name] = OpenAICompatibleProvider(name, resolved)

            print(
                f"[router] Loaded provider: {name} "
                f"(priority={resolved.get('priority', 99)}, free={resolved.get('free', False)})"
            )

    def _resolve_env(self, cfg: Dict) -> Dict:
        resolved = {}
        for key, value in cfg.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                resolved[key] = os.environ.get(env_var, "")
            elif isinstance(value, dict):
                resolved[key] = self._resolve_env(value)
            else:
                resolved[key] = value
        return resolved

    # ── Introspection ────────────────────────────────────────────

    def is_local(self, name: str) -> bool:
        provider = self.providers.get(name)
        if not provider:
            return name in LOCAL_PROVIDER_TYPES
        return bool(provider.config.get("local")) or name in LOCAL_PROVIDER_TYPES

    def supports_model(self, name: str, model: str) -> bool:
        """Whether a provider can serve ``model``.

        A declared ``models`` list is binding for every provider, local or not.
        Previously local providers were exempt on the grounds that Ollama serves
        whatever has been pulled, but that meant a request for ``gpt-4o`` would
        happily select Ollama and fail at dispatch. A local provider that really
        should accept anything can simply omit the list.
        """
        provider = self.providers.get(name)
        if not provider:
            return False
        models = provider.config.get("models", [])
        if not models:
            return True
        return model in models

    def resolve_target_alias(self, target: Optional[str]) -> Optional[str]:
        if not target:
            return None
        routing = self.config.get("routing", {})
        aliases = routing.get("target_aliases", {})
        return aliases.get(target, target)

    def provider_for_intent(self, intent: str) -> Optional[BaseProvider]:
        routing = self.config.get("routing", {})
        prefer = routing.get("prefer_targets", {})
        name = prefer.get(intent)
        if not name:
            return None
        name = self.resolve_target_alias(name) or name
        provider = self.providers.get(name)
        if provider and provider.can_execute():
            return provider
        return None

    def provider_by_name(
        self, name: str, model: Optional[str] = None
    ) -> Optional[BaseProvider]:
        """Look up a healthy provider by name or alias.

        When ``model`` is supplied the provider must actually be able to serve
        it. Without this check an intent-selected or client-supplied target
        silently accepts models it does not have.
        """
        resolved = self.resolve_target_alias(name) or name
        provider = self.providers.get(resolved)
        if not provider or not provider.can_execute():
            return None
        if model is not None and not self.supports_model(resolved, model):
            return None
        return provider

    # ── Selection ────────────────────────────────────────────────

    def eligible_providers(
        self,
        model: str,
        *,
        pool: Optional[Sequence[str]] = None,
        local_only: bool = False,
        exclude: Optional[Sequence[str]] = None,
    ) -> List[BaseProvider]:
        """Healthy providers that can serve ``model`` under the constraints.

        A profile's pool order is an explicit statement of preference and is
        preserved. Without a pool, ordering falls back to the cost policy:
        free first, then ascending priority.
        """
        resolved_pool: Optional[List[str]] = None
        if pool:
            resolved_pool = [self.resolve_target_alias(p) or p for p in pool]
        excluded = set(exclude or ())

        candidates = []
        for name, provider in self.providers.items():
            if name in excluded:
                continue
            if resolved_pool is not None and name not in resolved_pool:
                continue
            if local_only and not self.is_local(name):
                continue
            if not provider.can_execute():
                continue
            if not self.supports_model(name, model):
                continue

            if resolved_pool is not None:
                rank = (resolved_pool.index(name), 0, name)
            else:
                rank = (
                    int(not provider.config.get("free", False)),
                    provider.config.get("priority", 99),
                    name,
                )
            candidates.append((rank, provider))

        candidates.sort(key=lambda x: x[0])
        return [c[1] for c in candidates]

    def select_provider(
        self,
        model: str,
        policy: str = "cost",
        preferred_provider: Optional[str] = None,
        *,
        pool: Optional[Sequence[str]] = None,
        local_only: bool = False,
    ) -> Optional[BaseProvider]:
        if preferred_provider:
            p = self.provider_by_name(preferred_provider, model=model)
            if p and not (local_only and not self.is_local(p.name)):
                if not pool or p.name in [self.resolve_target_alias(x) or x for x in pool]:
                    return p

        candidates = self.eligible_providers(
            model, pool=pool, local_only=local_only
        )
        if not candidates:
            # A constrained pool that cannot serve the request falls back to the
            # unconstrained set, but an egress constraint never does: that would
            # defeat the point of local_only.
            if pool:
                candidates = self.eligible_providers(model, local_only=local_only)
            if not candidates:
                return None

        if policy == "quality":
            candidates.sort(
                key=lambda p: (
                    p.config.get("priority", 99),
                    not p.config.get("free", False),
                )
            )
        elif policy == "latency":
            candidates.sort(
                key=lambda p: (
                    p.config.get("timeout_seconds", 60),
                    p.config.get("priority", 99),
                )
            )
        return candidates[0]

    def build_route_chain(
        self,
        model: str,
        *,
        preferred_provider: Optional[str] = None,
        fallback_provider: Optional[str] = None,
        pool: Optional[Sequence[str]] = None,
        local_only: bool = False,
        max_attempts: int = 3,
    ) -> List[BaseProvider]:
        """Ordered providers to try for this request.

        Returned up front rather than discovered on failure, so the caller walks
        a known chain instead of guessing a single replacement after an error.
        """
        chain: List[BaseProvider] = []

        def _append(provider: Optional[BaseProvider]):
            if provider and all(p.name != provider.name for p in chain):
                chain.append(provider)

        if preferred_provider:
            p = self.provider_by_name(preferred_provider, model=model)
            if p and not (local_only and not self.is_local(p.name)):
                _append(p)

        for provider in self.eligible_providers(model, pool=pool, local_only=local_only):
            _append(provider)

        if fallback_provider:
            fb = self.provider_by_name(fallback_provider, model=model)
            if fb and not (local_only and not self.is_local(fb.name)):
                _append(fb)

        if not chain and pool:
            for provider in self.eligible_providers(model, local_only=local_only):
                _append(provider)

        return chain[:max_attempts]

    async def route_with_fallback(
        self,
        model: str,
        request: Any = None,
        preferred_provider: Optional[str] = None,
        fallback_provider: Optional[str] = None,
        *,
        pool: Optional[Sequence[str]] = None,
        local_only: bool = False,
    ) -> tuple[Optional[BaseProvider], bool]:
        chain = self.build_route_chain(
            model,
            preferred_provider=preferred_provider,
            fallback_provider=fallback_provider,
            pool=pool,
            local_only=local_only,
        )
        if not chain:
            return None, False
        primary = chain[0]
        used_fallback = bool(
            preferred_provider
            and (self.resolve_target_alias(preferred_provider) or preferred_provider)
            != primary.name
        )
        return primary, used_fallback

    def select_fallback(
        self,
        failed_name: str,
        model: str,
        fallback_provider: Optional[str] = None,
        *,
        pool: Optional[Sequence[str]] = None,
        local_only: bool = False,
    ) -> Optional[BaseProvider]:
        if fallback_provider:
            p = self.provider_by_name(fallback_provider, model=model)
            if p and p.name != failed_name and not (local_only and not self.is_local(p.name)):
                return p

        candidates = self.eligible_providers(
            model, pool=pool, local_only=local_only, exclude=[failed_name]
        )
        if not candidates and pool:
            candidates = self.eligible_providers(
                model, local_only=local_only, exclude=[failed_name]
            )
        return candidates[0] if candidates else None

    async def health_check_all(self) -> List[Dict]:
        results = []
        for name, provider in self.providers.items():
            healthy = await provider.health_check()
            results.append({
                "name": name,
                "healthy": healthy,
                "circuit_state": provider.circuit_state.value,
                "models": provider.config.get("models", []),
                "priority": provider.config.get("priority", 99),
                "free": provider.config.get("free", False),
                "local": self.is_local(name),
                "failure_count": provider.failure_count,
            })
        return results

    async def close(self):
        for provider in self.providers.values():
            if hasattr(provider, "close"):
                await provider.close()
