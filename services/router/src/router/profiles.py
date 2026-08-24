"""Route profiles.

An intent does not select a provider, it selects a *profile*: the eligible
provider pool, the model, generation parameters, an optional system prompt,
cache behaviour and whether retrieval applies. Mapping an intent straight to a
provider name (the previous `prefer_targets` design) left the model and
everything else unspecified, so the routing decision was only half made.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CachePolicy:
    enabled: bool = True
    # None means "inherit the global semantic threshold".
    distance_threshold: Optional[float] = None
    partition: bool = True

    @classmethod
    def from_dict(cls, raw: Any) -> "CachePolicy":
        if raw is None:
            return cls()
        if isinstance(raw, bool):
            return cls(enabled=raw)
        raw = raw or {}
        threshold = raw.get("distance_threshold")
        return cls(
            enabled=bool(raw.get("enabled", True)),
            distance_threshold=float(threshold) if threshold is not None else None,
            partition=bool(raw.get("partition", True)),
        )


@dataclass
class RouteProfile:
    name: str
    pool: List[str] = field(default_factory=list)
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    system_prompt: Optional[str] = None
    retrieval: bool = False
    retrieval_top_k: int = 4
    cache: CachePolicy = field(default_factory=CachePolicy)

    @classmethod
    def from_dict(cls, name: str, raw: Dict[str, Any] | None) -> "RouteProfile":
        raw = raw or {}
        pool = raw.get("pool") or []
        if isinstance(pool, str):
            pool = [pool]
        temperature = raw.get("temperature")
        max_tokens = raw.get("max_tokens")
        return cls(
            name=name,
            pool=[str(p) for p in pool],
            model=raw.get("model"),
            temperature=float(temperature) if temperature is not None else None,
            max_tokens=int(max_tokens) if max_tokens is not None else None,
            system_prompt=raw.get("system_prompt"),
            retrieval=bool(raw.get("retrieval", False)),
            retrieval_top_k=int(raw.get("retrieval_top_k", 4)),
            cache=CachePolicy.from_dict(raw.get("cache")),
        )


DEFAULT_PROFILE = RouteProfile(name="default")


class ProfileRegistry:
    """Resolves intent -> profile, with a `default` fallback."""

    def __init__(
        self,
        profiles: Dict[str, RouteProfile],
        intent_map: Dict[str, str],
        default_profile: str = "default",
    ):
        self.profiles = profiles
        self.intent_map = intent_map
        self.default_profile = default_profile

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "ProfileRegistry":
        routing = (config or {}).get("routing", {}) or {}

        profiles: Dict[str, RouteProfile] = {}
        for name, raw in (routing.get("profiles") or {}).items():
            profiles[name] = RouteProfile.from_dict(name, raw)

        intent_map: Dict[str, str] = {}
        for intent, spec in (routing.get("intents") or {}).items():
            if isinstance(spec, dict) and spec.get("profile"):
                intent_map[intent] = str(spec["profile"])

        # Legacy `prefer_targets: {intent: provider}` still works: each entry
        # becomes a single-provider pool so existing configs keep routing.
        for intent, provider in (routing.get("prefer_targets") or {}).items():
            if intent in intent_map:
                continue
            synthetic = f"legacy_{intent}"
            profiles.setdefault(
                synthetic, RouteProfile(name=synthetic, pool=[str(provider)])
            )
            intent_map[intent] = synthetic

        default_name = str(routing.get("default_profile", "default"))
        profiles.setdefault(default_name, RouteProfile(name=default_name))

        return cls(profiles, intent_map, default_name)

    def for_intent(self, intent: str) -> RouteProfile:
        name = self.intent_map.get(intent)
        if name and name in self.profiles:
            return self.profiles[name]
        return self.profiles.get(self.default_profile, DEFAULT_PROFILE)

    def get(self, name: str) -> Optional[RouteProfile]:
        return self.profiles.get(name)
