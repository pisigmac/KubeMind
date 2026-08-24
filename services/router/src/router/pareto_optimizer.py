"""Dynamic Latency & Cost Pareto Frontier Optimizer for KubeMind Gateway.

Computes the Pareto-optimal trade-off surface across Time-To-First-Token (TTFT) latency,
dollar cost per 1k tokens, and empirical quality benchmarks to dynamically pick
the optimal model for SLA constraints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class ProviderCandidate:
    name: str
    model: str
    cost_per_1k_usd: float
    avg_latency_ms: float
    quality_score: float  # [0.0 - 1.0]
    available: bool = True


@dataclass
class ParetoSelection:
    selected_candidate: ProviderCandidate
    is_pareto_optimal: bool
    rationale: str
    frontier_candidates: List[str]


class ParetoRouterOptimizer:
    """Selects the optimal provider candidate on the cost vs latency Pareto frontier."""

    def __init__(self, default_max_latency_ms: float = 1200.0, default_max_cost_usd: float = 0.05):
        self.default_max_latency_ms = default_max_latency_ms
        self.default_max_cost_usd = default_max_cost_usd

    def compute_pareto_frontier(self, candidates: List[ProviderCandidate]) -> List[ProviderCandidate]:
        """
        Calculates non-dominated candidates where no other candidate has BOTH
        lower cost AND lower latency while maintaining at least equal quality.
        """
        available = [c for c in candidates if c.available]
        if not available:
            return []

        frontier: List[ProviderCandidate] = []

        for candidate in available:
            dominated = False
            for other in available:
                if other == candidate:
                    continue
                # If 'other' is strictly better or equal in cost, latency, AND quality
                if (
                    other.cost_per_1k_usd <= candidate.cost_per_1k_usd
                    and other.avg_latency_ms <= candidate.avg_latency_ms
                    and other.quality_score >= candidate.quality_score
                    and (
                        other.cost_per_1k_usd < candidate.cost_per_1k_usd
                        or other.avg_latency_ms < candidate.avg_latency_ms
                        or other.quality_score > candidate.quality_score
                    )
                ):
                    dominated = True
                    break

            if not dominated:
                frontier.append(candidate)

        return frontier

    def select_best_candidate(
        self,
        candidates: List[ProviderCandidate],
        max_latency_ms: Optional[float] = None,
        max_cost_usd: Optional[float] = None,
        prioritize_cost: bool = True,
    ) -> Optional[ParetoSelection]:
        """
        Selects the top candidate on the Pareto frontier satisfying the latency/cost SLA.
        """
        frontier = self.compute_pareto_frontier(candidates)
        if not frontier:
            return None

        max_lat = max_latency_ms or self.default_max_latency_ms
        max_c = max_cost_usd or self.default_max_cost_usd

        # Filter frontier by hard SLA bounds
        eligible = [c for c in frontier if c.avg_latency_ms <= max_lat and c.cost_per_1k_usd <= max_c]

        # Fall back to least cost in frontier if hard bounds miss
        pool = eligible if eligible else frontier

        if prioritize_cost:
            # Sort primarily by lowest cost, then highest quality
            sorted_pool = sorted(pool, key=lambda x: (x.cost_per_1k_usd, -x.quality_score))
            rationale = "Selected lowest cost candidate on Pareto frontier satisfying SLA."
        else:
            # Sort primarily by lowest latency, then highest quality
            sorted_pool = sorted(pool, key=lambda x: (x.avg_latency_ms, -x.quality_score))
            rationale = "Selected lowest latency candidate on Pareto frontier satisfying SLA."

        chosen = sorted_pool[0]
        return ParetoSelection(
            selected_candidate=chosen,
            is_pareto_optimal=True,
            rationale=rationale,
            frontier_candidates=[c.name for c in frontier],
        )


_GLOBAL_PARETO = ParetoRouterOptimizer()


def get_default_pareto_optimizer() -> ParetoRouterOptimizer:
    return _GLOBAL_PARETO
