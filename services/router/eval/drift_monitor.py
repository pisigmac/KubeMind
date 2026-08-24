"""Synthetic Ground-Truth Benchmark & Accuracy Drift Monitor for KubeMind.

Runs periodic evaluation across holdout test sets to detect classification accuracy
drift, semantic degradation, and regressions over time.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple


@dataclass
class DriftBenchmarkSample:
    prompt: str
    expected_intent: str
    category: str


# Golden holdout dataset for accuracy drift detection
GOLDEN_DRIFT_BENCHMARK = [
    DriftBenchmarkSample("Fix the python zero division error in auth.py", "code", "dev"),
    DriftBenchmarkSample("What are the quarterly travel expense limits in our handbook?", "rag", "policy"),
    DriftBenchmarkSample("Write a simple regex to validate emails", "code", "dev"),
    DriftBenchmarkSample("How do I request access to the production Kubernetes cluster?", "rag", "ops"),
    DriftBenchmarkSample("Write a creative bedtime story about a friendly dragon", "general", "creative"),
    DriftBenchmarkSample("Summarize the main differences between TCP and UDP", "general", "knowledge"),
]


@dataclass
class DriftReport:
    timestamp: float
    total_samples: int
    correct_samples: int
    accuracy_pct: float
    drift_detected: bool
    baseline_accuracy_pct: float
    details: List[Dict[str, Any]] = field(default_factory=list)


class AccuracyDriftMonitor:
    """Monitors live and synthetic classifier accuracy against historical baselines."""

    def __init__(self, baseline_accuracy_pct: float = 90.0, max_allowed_drop_pct: float = 10.0):
        self.baseline_accuracy_pct = baseline_accuracy_pct
        self.max_allowed_drop_pct = max_allowed_drop_pct
        self.history: List[DriftReport] = []

    def evaluate_classifier(
        self, classifier_fn: Callable[[str], str]
    ) -> DriftReport:
        """Runs the golden benchmark against the provided intent classification function."""
        correct = 0
        details = []

        for sample in GOLDEN_DRIFT_BENCHMARK:
            pred = classifier_fn(sample.prompt)
            is_correct = (pred.lower() == sample.expected_intent.lower())
            if is_correct:
                correct += 1

            details.append({
                "prompt": sample.prompt,
                "expected": sample.expected_intent,
                "predicted": pred,
                "is_correct": is_correct,
            })

        total = len(GOLDEN_DRIFT_BENCHMARK)
        acc_pct = round((correct / total) * 100.0, 2)
        drift = (self.baseline_accuracy_pct - acc_pct) > self.max_allowed_drop_pct

        report = DriftReport(
            timestamp=time.time(),
            total_samples=total,
            correct_samples=correct,
            accuracy_pct=acc_pct,
            drift_detected=drift,
            baseline_accuracy_pct=self.baseline_accuracy_pct,
            details=details,
        )

        self.history.append(report)
        return report


_GLOBAL_DRIFT_MONITOR = AccuracyDriftMonitor()


def get_default_drift_monitor() -> AccuracyDriftMonitor:
    return _GLOBAL_DRIFT_MONITOR
