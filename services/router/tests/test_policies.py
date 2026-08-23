"""Routing policies and the latency budget.

Before this, `cost`, `quality` and `latency` all sorted on `priority` or on the
configured timeout, so the three were indistinguishable and `max_latency_ms`
was accepted and never read.
"""

import pytest

from router.providers.registry import ProviderRegistry
from tests.test_routing import FakeProvider


@pytest.fixture
def registry():
    r = ProviderRegistry()
    r.config = {}
    r.providers = {
        # Cheapest, but ranked worst on quality and slow in practice.
        "ollama": FakeProvider(
            "ollama",
            {"local": True, "priority": 1, "free": True, "quality_rank": 5},
        ),
        "groq": FakeProvider(
            "groq", {"priority": 3, "free": True, "quality_rank": 3}
        ),
        # Most expensive, best quality.
        "openai": FakeProvider(
            "openai", {"priority": 6, "free": False, "quality_rank": 1}
        ),
    }
    return r


def _names(providers):
    return [p.name for p in providers]


class TestPoliciesDiffer:
    def test_cost_prefers_free_then_priority(self, registry):
        assert _names(registry.eligible_providers("m", policy="cost")) == [
            "ollama",
            "groq",
            "openai",
        ]

    def test_quality_uses_its_own_rank(self, registry):
        # Exactly reversed from cost, which is the point: if quality still
        # sorted on priority the two policies would be the same function.
        assert _names(registry.eligible_providers("m", policy="quality")) == [
            "openai",
            "groq",
            "ollama",
        ]

    def test_latency_uses_measurements(self, registry):
        registry.providers["ollama"].observe_latency(900)
        registry.providers["groq"].observe_latency(120)
        registry.providers["openai"].observe_latency(400)
        assert _names(registry.eligible_providers("m", policy="latency")) == [
            "groq",
            "openai",
            "ollama",
        ]

    def test_unmeasured_provider_is_not_assumed_fast(self, registry):
        registry.providers["groq"].observe_latency(120)
        # ollama and openai have no samples, so they sort after the one we know
        # is fast rather than jumping ahead on an assumption.
        assert _names(registry.eligible_providers("m", policy="latency"))[0] == "groq"

    def test_unknown_policy_falls_back_to_cost(self, registry):
        assert _names(registry.eligible_providers("m", policy="nonsense")) == _names(
            registry.eligible_providers("m", policy="cost")
        )


class TestLatencyObservation:
    def test_ewma_smooths_samples(self, registry):
        p = registry.providers["groq"]
        p.observe_latency(100)
        p.observe_latency(200)
        # Weighted toward history, so one slow call does not reroute traffic.
        assert 100 < p.observed_latency_ms < 150
        assert p.latency_samples == 2

    def test_no_samples_means_no_estimate(self, registry):
        assert registry.providers["groq"].observed_latency_ms is None

    def test_non_positive_samples_ignored(self, registry):
        p = registry.providers["groq"]
        p.observe_latency(0)
        p.observe_latency(-5)
        assert p.observed_latency_ms is None

    def test_quality_rank_defaults_to_priority(self):
        p = FakeProvider("x", {"priority": 7})
        assert p.quality_rank == 7


class TestLatencyBudget:
    def test_budget_excludes_measured_slow_providers(self, registry):
        registry.providers["ollama"].observe_latency(2000)
        registry.providers["groq"].observe_latency(100)
        names = _names(registry.eligible_providers("m", max_latency_ms=500))
        assert "ollama" not in names
        assert "groq" in names

    def test_unmeasured_provider_survives_the_budget(self, registry):
        # Evicting a provider nobody has timed would be a guess dressed up as
        # a limit.
        registry.providers["groq"].observe_latency(100)
        names = _names(registry.eligible_providers("m", max_latency_ms=500))
        assert "openai" in names

    def test_impossible_budget_returns_closest_rather_than_failing(self, registry):
        for name, ms in (("ollama", 2000), ("groq", 1500), ("openai", 3000)):
            registry.providers[name].observe_latency(ms)
        names = _names(registry.eligible_providers("m", max_latency_ms=100))
        # A soft preference should not turn into a failed request.
        assert names and names[0] == "groq"

    def test_budget_reaches_the_route_chain(self, registry):
        registry.providers["ollama"].observe_latency(2000)
        registry.providers["groq"].observe_latency(100)
        chain = _names(
            registry.build_route_chain("m", max_latency_ms=500, policy="cost")
        )
        assert "ollama" not in chain

    def test_policy_reaches_the_route_chain(self, registry):
        assert _names(registry.build_route_chain("m", policy="quality"))[0] == "openai"


class TestPoolStillWins:
    def test_pool_order_overrides_policy(self, registry):
        # A profile pool is an explicit preference; policy orders only when the
        # profile has not already decided.
        names = _names(
            registry.eligible_providers("m", pool=["openai", "ollama"], policy="cost")
        )
        assert names == ["openai", "ollama"]
