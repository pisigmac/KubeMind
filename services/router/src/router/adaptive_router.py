"""Adaptive Auto-Calibrating Softmax Router for KubeMind Intent Classifier.

Dynamically tunes softmax temperature (T) and confidence margins based on
downstream user feedback, latency budgets, and classification accuracy metrics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class CalibrationState:
    temperature: float = 1.0
    min_confidence: float = 0.55
    min_margin: float = 0.15
    total_samples: int = 0
    positive_feedback_count: int = 0
    negative_feedback_count: int = 0


class AdaptiveRouterCalibrator:
    """Online calibrator for intent classification logits and confidence gates."""

    def __init__(
        self,
        initial_temperature: float = 1.0,
        initial_min_confidence: float = 0.55,
        adaptation_rate: float = 0.05,
    ):
        self.state = CalibrationState(
            temperature=initial_temperature,
            min_confidence=initial_min_confidence,
        )
        self.adaptation_rate = adaptation_rate

    def apply_temperature(self, logits: Dict[str, float]) -> Dict[str, float]:
        """Scale raw logits by the learned temperature T and compute softmax probabilities."""
        if not logits:
            return {}

        t = max(0.1, self.state.temperature)
        scaled = {k: v / t for k, v in logits.items()}
        max_val = max(scaled.values())
        exp_vals = {k: math.exp(v - max_val) for k, v in scaled.items()}
        total = sum(exp_vals.values())

        if total == 0:
            return {k: 1.0 / len(logits) for k in logits}
        return {k: round(v / total, 4) for k, v in exp_vals.items()}

    def evaluate_intent(self, probabilities: Dict[str, float]) -> Tuple[str, float, float, bool]:
        """
        Returns (top_intent, confidence, margin, should_abstain).
        """
        if not probabilities:
            return "general", 0.0, 0.0, True

        sorted_items = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)
        top_intent, top_conf = sorted_items[0]
        second_conf = sorted_items[1][1] if len(sorted_items) > 1 else 0.0
        margin = round(top_conf - second_conf, 4)

        abstained = (top_conf < self.state.min_confidence) or (margin < self.state.min_margin)
        return top_intent, top_conf, margin, abstained

    def record_feedback(self, success: bool, latency_ms: float = 0.0) -> None:
        """Online adaptive calibration update loop."""
        self.state.total_samples += 1
        if success:
            self.state.positive_feedback_count += 1
            # Gradually reward calibration: lower margin slightly to allow more confident routing
            self.state.min_margin = max(0.08, self.state.min_margin - (self.adaptation_rate * 0.01))
            self.state.temperature = max(0.5, self.state.temperature - (self.adaptation_rate * 0.01))
        else:
            self.state.negative_feedback_count += 1
            # Misroute penalization: increase temperature to soften over-confidence and raise margin
            self.state.min_margin = min(0.35, self.state.min_margin + (self.adaptation_rate * 0.05))
            self.state.temperature = min(2.0, self.state.temperature + (self.adaptation_rate * 0.05))

    def get_stats(self) -> Dict[str, Any]:
        """Return current calibration telemetry."""
        pos = self.state.positive_feedback_count
        tot = self.state.total_samples
        accuracy = (pos / tot) if tot > 0 else 1.0
        return {
            "temperature": round(self.state.temperature, 4),
            "min_confidence": round(self.state.min_confidence, 4),
            "min_margin": round(self.state.min_margin, 4),
            "total_samples": tot,
            "estimated_accuracy": round(accuracy, 4),
        }
