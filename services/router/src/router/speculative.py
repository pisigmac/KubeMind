"""Dynamic Cost-Aware Speculative Decoding Orchestrator for KubeMind.

Accelerates inference by combining fast, lightweight local draft models
with high-tier verifier models in parallel, cutting TTFT and cost.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class SpeculativeResult:
    final_text: str
    draft_tokens_generated: int
    tokens_accepted: int
    acceptance_rate: float
    latency_ms: float
    cost_saved_usd: float


class SpeculativeDecodingOrchestrator:
    """Coordinates speculative draft execution and target model validation."""

    def __init__(self, target_verifier_cost_per_1k: float = 0.015, draft_cost_per_1k: float = 0.000):
        self.target_verifier_cost_per_1k = target_verifier_cost_per_1k
        self.draft_cost_per_1k = draft_cost_per_1k

    async def execute_speculative_turn(
        self,
        prompt: str,
        draft_fn: Callable[[str], str],
        verifier_fn: Callable[[str, str], Tuple[str, int, int]],
    ) -> SpeculativeResult:
        """
        Executes a speculative turn:
        1. Generates speculative draft candidate from fast local model
        2. Validates candidate prefix in verifier model
        """
        start_time = time.perf_counter()

        # Step 1: Fast local draft generation
        draft_text = draft_fn(prompt)
        draft_token_count = max(1, len(draft_text.split()))

        # Step 2: Target verification & continuation
        final_text, accepted_count, total_count = verifier_fn(prompt, draft_text)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        acc_rate = round(accepted_count / max(1, total_count), 3)

        # Cost savings computation: accepted tokens did not require full autoregressive decode
        tokens_saved = accepted_count
        cost_saved = (tokens_saved / 1000.0) * self.target_verifier_cost_per_1k

        return SpeculativeResult(
            final_text=final_text,
            draft_tokens_generated=draft_token_count,
            tokens_accepted=accepted_count,
            acceptance_rate=acc_rate,
            latency_ms=round(elapsed_ms, 2),
            cost_saved_usd=round(cost_saved, 6),
        )


_GLOBAL_SPECULATIVE = SpeculativeDecodingOrchestrator()


def get_default_speculative() -> SpeculativeDecodingOrchestrator:
    return _GLOBAL_SPECULATIVE
