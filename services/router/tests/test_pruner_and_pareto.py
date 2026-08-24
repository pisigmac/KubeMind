"""Unit tests for Semantic Cache Pruner and Pareto Frontier Optimizer."""

import time
import pytest
from router.cache.pruner import SemanticCachePruner
from router.pareto_optimizer import ParetoRouterOptimizer, ProviderCandidate


def test_semantic_cache_pruning_and_pinning():
    pruner = SemanticCachePruner(default_ttl_seconds=10.0)

    # Insert 3 entries
    pruner.record_access("sig-1", "ws-a")
    pruner.record_access("sig-2", "ws-a")
    pruner.record_access("sig-3", "ws-a")

    # Pin sig-1
    pruner.pin_entry("sig-1")

    # Evaluate pruning at t + 15s (sig-2 and sig-3 expire, sig-1 remains because pinned)
    now = time.time() + 15.0
    report = pruner.evaluate_pruning(current_time=now)

    assert report.pruned_count == 2
    assert report.preserved_count == 1
    assert "sig-1" not in report.evicted_signatures
    assert "sig-2" in report.evicted_signatures


def test_pareto_frontier_cost_optimization():
    optimizer = ParetoRouterOptimizer()

    candidates = [
        ProviderCandidate(name="local-ollama", model="llama3.1:8b", cost_per_1k_usd=0.000, avg_latency_ms=180.0, quality_score=0.82),
        ProviderCandidate(name="cloud-fast", model="gpt-4o-mini", cost_per_1k_usd=0.002, avg_latency_ms=250.0, quality_score=0.88),
        ProviderCandidate(name="cloud-high", model="claude-3-5-sonnet", cost_per_1k_usd=0.015, avg_latency_ms=800.0, quality_score=0.96),
        # Dominated candidate (higher latency and higher cost for lower quality)
        ProviderCandidate(name="slow-legacy", model="legacy-7b", cost_per_1k_usd=0.020, avg_latency_ms=1200.0, quality_score=0.75),
    ]

    frontier = optimizer.compute_pareto_frontier(candidates)
    names = [c.name for c in frontier]

    assert "local-ollama" in names
    assert "cloud-fast" in names
    assert "cloud-high" in names
    assert "slow-legacy" not in names  # Correctly identified as dominated

    # Pick best candidate prioritizing cost
    selection = optimizer.select_best_candidate(candidates, prioritize_cost=True)
    assert selection is not None
    assert selection.selected_candidate.name == "local-ollama"
