"""Unit tests for Wasm Hooks and Adaptive Auto-Calibrating Router."""

import pytest
from router.adaptive_router import AdaptiveRouterCalibrator
from kubemind_policy.wasm_hooks import HookContext, HookResult, WasmHookRunner


def test_wasm_pre_hook_transformation():
    runner = WasmHookRunner()

    def uppercase_hook(text: str, ctx: HookContext) -> HookResult:
        return HookResult(allowed=True, modified_text=text.upper())

    runner.register_pre_hook(uppercase_hook)
    ctx = HookContext(workspace_id="test", model="llama3.1", intent="general")
    res = runner.execute_pre_hooks("hello world", ctx)

    assert res.allowed is True
    assert res.modified_text == "HELLO WORLD"


def test_wasm_pre_hook_block():
    runner = WasmHookRunner()

    def regulatory_block_hook(text: str, ctx: HookContext) -> HookResult:
        if "prohibited_action" in text:
            return HookResult(allowed=False, action="block", reason="Regulatory violation")
        return HookResult(allowed=True)

    runner.register_pre_hook(regulatory_block_hook)
    ctx = HookContext(workspace_id="test", model="llama3.1", intent="general")
    res = runner.execute_pre_hooks("execute prohibited_action now", ctx)

    assert res.allowed is False
    assert res.action == "block"
    assert "Regulatory violation" in res.reason


def test_adaptive_router_temperature_and_feedback():
    calibrator = AdaptiveRouterCalibrator(initial_temperature=1.0, initial_min_confidence=0.5)
    raw_logits = {"code": 2.5, "general": 1.0, "rag": 0.5}

    probs = calibrator.apply_temperature(raw_logits)
    assert sum(probs.values()) == pytest.approx(1.0, abs=1e-2)
    assert probs["code"] > probs["general"]

    intent, conf, margin, abstained = calibrator.evaluate_intent(probs)
    assert intent == "code"
    assert abstained is False

    # Penalize with negative feedback (simulating misroute)
    initial_margin = calibrator.state.min_margin
    calibrator.record_feedback(success=False)
    assert calibrator.state.min_margin > initial_margin
    assert calibrator.state.temperature > 1.0
