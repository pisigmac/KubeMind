"""Unit tests for Network Guard, Accuracy Drift Monitor, and Speculative Decoding."""

import pytest
from kubemind_policy.network_guard import NetworkEgressGuard
from eval.drift_monitor import AccuracyDriftMonitor
from router.speculative import SpeculativeDecodingOrchestrator


def test_network_egress_guard_approved_host():
    guard = NetworkEgressGuard()
    verdict = guard.verify_egress_target("https://api.openai.com/v1/chat/completions")
    assert verdict.allowed is True
    assert verdict.action == "allow"


def test_network_egress_guard_blocked_host():
    guard = NetworkEgressGuard()
    verdict = guard.verify_egress_target("https://malicious-exfiltration-site.com/steal-keys")
    assert verdict.allowed is False
    assert verdict.action == "block"
    assert "Anti-Exfiltration Rule" in verdict.reason


def test_accuracy_drift_monitor():
    monitor = AccuracyDriftMonitor(baseline_accuracy_pct=85.0)

    # Simulated classifier
    def mock_classifier(prompt: str) -> str:
        if "handbook" in prompt or "kubernetes" in prompt.lower():
            return "rag"
        if "python" in prompt or "regex" in prompt:
            return "code"
        return "general"

    report = monitor.evaluate_classifier(mock_classifier)

    assert report.total_samples == 6
    assert report.correct_samples == 6
    assert report.accuracy_pct == 100.0
    assert report.drift_detected is False


@pytest.mark.asyncio
async def test_speculative_decoding_orchestrator():
    orchestrator = SpeculativeDecodingOrchestrator(target_verifier_cost_per_1k=0.015)

    def draft_fn(prompt: str) -> str:
        return "The capital of France is Paris."

    def verifier_fn(prompt: str, draft: str):
        # Full verifier accepts the 6 draft tokens and continues
        return f"{draft} It is known for the Eiffel Tower.", 6, 12

    res = await orchestrator.execute_speculative_turn(
        prompt="Where is Paris?",
        draft_fn=draft_fn,
        verifier_fn=verifier_fn,
    )

    assert res.tokens_accepted == 6
    assert res.acceptance_rate == 0.5
    assert res.cost_saved_usd > 0.0
    assert "Eiffel Tower" in res.final_text
