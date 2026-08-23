import os
import yaml  # type: ignore[import-untyped]  # Runtime dependency is pinned; stubs are dev-only.
from typing import Dict, List, Optional, Any, Sequence

from router.providers.base import BaseProvider
from router.providers.keymint_managed import KeyMintManagedProvider
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
        self.credential_mode: Optional[str] = None
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
        mode = os.environ.get(
            "KUBEMIND_CREDENTIAL_MODE", str(self.config.get("credential_mode") or "")
        ).strip().lower()
        if mode not in {"keymint", "direct"}:
            raise ValueError(
                "credential_mode must be explicitly configured as keymint or direct"
            )
        from kubemind_auth import is_production

        if is_production() and mode == "direct":
            raise ValueError(
                "KUBEMIND_DEPLOYMENT=production refuses direct credential mode; "
                "set KUBEMIND_CREDENTIAL_MODE=keymint"
            )
        self.credential_mode = mode
        for name, cfg in self.config.get("providers", {}).items():
            resolved = self._resolve_env(cfg)
            is_local = bool(resolved.get("local")) or name in LOCAL_PROVIDER_TYPES

            if mode == "keymint":
                if "api_key" in resolved or "api_key" in cfg:
                    raise ValueError(
                        f"Provider {name} must use a KeyMint Connection; "
                        "ambient api_key configuration is forbidden"
                    )
                self.providers[name] = KeyMintManagedProvider(name, resolved)
                print(f"[router] Loaded KeyMint-managed provider metadata: {name}")
                continue

            if not is_local and not resolved.get("api_key"):
                print(f"[router] Skipping direct provider {name}: no API key configured")
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

        # Share breaker state across replicas when Redis is available.
        redis_client = getattr(self.cache, "client", None) if self.cache else None
        if redis_client:
            for provider in self.providers.values():
                provider.bind_circuit_redis(redis_client)

    def _resolve_env(self, cfg: Dict) -> Dict:
        resolved: Dict[str, Any] = {}
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

    @property
    def uses_keymint(self) -> bool:
        return self.credential_mode == "keymint"

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

    def _rank(
        self, provider: BaseProvider, policy: str
    ) -> tuple:
        """Ordering key for a provider under a routing policy.

        The three policies were previously indistinguishable -- `quality` and
        `cost` both sorted on `priority`, and `latency` sorted on the
        configured timeout, which is an operator's guess rather than a
        measurement.
        """
        name = provider.name
        if policy == "quality":
            return (provider.quality_rank, provider.config.get("priority", 99), name)
        if policy == "latency":
            observed = provider.observed_latency_ms
            # Unmeasured providers sort after measured ones rather than being
            # assumed fast, but stay ahead of anything known to be slow.
            return (
                0 if observed is not None else 1,
                observed if observed is not None else 0.0,
                provider.config.get("priority", 99),
                name,
            )
        # cost (default): free first, then ascending priority
        return (
            int(not provider.config.get("free", False)),
            provider.config.get("priority", 99),
            name,
        )

    def eligible_providers(
        self,
        model: str,
        *,
        pool: Optional[Sequence[str]] = None,
        local_only: bool = False,
        exclude: Optional[Sequence[str]] = None,
        policy: str = "cost",
        max_latency_ms: Optional[int] = None,
        keymint_managed: bool = False,
    ) -> List[BaseProvider]:
        """Healthy providers that can serve ``model`` under the constraints.

        A profile's pool order is an explicit statement of preference and is
        preserved. Without a pool, ordering follows ``policy``.
        """
        resolved_pool: Optional[List[str]] = None
        if pool:
            resolved_pool = [self.resolve_target_alias(p) or p for p in pool]
        excluded = set(exclude or ())

        candidates = []
        over_budget = []
        for name, provider in self.providers.items():
            if name in excluded:
                continue
            if resolved_pool is not None and name not in resolved_pool:
                continue
            if local_only and not self.is_local(name):
                continue
            if keymint_managed:
                can_execute = isinstance(
                    provider, KeyMintManagedProvider
                ) and provider.can_route_via_keymint()
            else:
                can_execute = provider.can_execute()
            if not can_execute:
                continue
            if not self.supports_model(name, model):
                continue

            if resolved_pool is not None:
                rank = (resolved_pool.index(name), 0, name)
            else:
                rank = self._rank(provider, policy)

            if max_latency_ms is not None:
                observed = provider.observed_latency_ms
                # Only a measured provider can bust a budget. Evicting one that
                # has never been called would be a guess dressed up as a limit.
                if observed is not None and observed > max_latency_ms:
                    over_budget.append((rank, provider))
                    continue
            candidates.append((rank, provider))

        if not candidates and over_budget:
            # Nothing meets the budget. Returning the closest is better than
            # failing the request over a soft preference.
            over_budget.sort(key=lambda x: (x[1].observed_latency_ms or 0.0))
            return [p for _, p in over_budget]

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
        max_latency_ms: Optional[int] = None,
    ) -> Optional[BaseProvider]:
        if preferred_provider:
            p = self.provider_by_name(preferred_provider, model=model)
            if p and not (local_only and not self.is_local(p.name)):
                if not pool or p.name in [self.resolve_target_alias(x) or x for x in pool]:
                    return p

        candidates = self.eligible_providers(
            model,
            pool=pool,
            local_only=local_only,
            policy=policy,
            max_latency_ms=max_latency_ms,
        )
        if not candidates:
            # A constrained pool that cannot serve the request falls back to the
            # unconstrained set, but an egress constraint never does: that would
            # defeat the point of local_only.
            if pool:
                candidates = self.eligible_providers(
                    model,
                    local_only=local_only,
                    policy=policy,
                    max_latency_ms=max_latency_ms,
                )
            if not candidates:
                return None
        return candidates[0]

    def build_route_chain(
        self,
        model: str,
        *,
        preferred_provider: Optional[str] = None,
        fallback_provider: Optional[str] = None,
        pool: Optional[Sequence[str]] = None,
        local_only: bool = False,
        policy: str = "cost",
        max_latency_ms: Optional[int] = None,
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

        for provider in self.eligible_providers(
            model,
            pool=pool,
            local_only=local_only,
            policy=policy,
            max_latency_ms=max_latency_ms,
        ):
            _append(provider)

        if fallback_provider:
            fb = self.provider_by_name(fallback_provider, model=model)
            if fb and not (local_only and not self.is_local(fb.name)):
                _append(fb)

        if not chain and pool:
            for provider in self.eligible_providers(
                model, local_only=local_only, policy=policy
            ):
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
                "quality_rank": provider.quality_rank,
                "observed_latency_ms": (
                    round(provider.observed_latency_ms, 1)
                    if provider.observed_latency_ms is not None
                    else None
                ),
                "latency_samples": provider.latency_samples,
                "free": provider.config.get("free", False),
                "local": self.is_local(name),
                "failure_count": provider.failure_count,
            })
        return results

    async def close(self):
        for provider in self.providers.values():
            if hasattr(provider, "close"):
                await provider.close()
