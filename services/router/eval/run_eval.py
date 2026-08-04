#!/usr/bin/env python3
"""Scored evaluation harness for intent classification and policy.

Two things it exists to prevent:

1. Tuning thresholds by feel. Every number in the classifier config should be
   justified by a sweep against a held-out set.
2. Hiding the errors that matter behind an average. A code prompt landing on a
   general model is a minor quality regression; a prompt containing a secret
   reaching a cloud provider is an incident. Those are not the same error and
   are not averaged together here.

The dataset is held out from the examples that build the index -- scoring the
classifier on its own examples measures memorisation, not generalisation.

Usage::

    python eval/run_eval.py                     # score at configured thresholds
    python eval/run_eval.py --sweep             # accuracy vs abstention curve
    python eval/run_eval.py --embeddings cache.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT.parents[1] / "shared" / "python"))

import yaml  # noqa: E402

from router.intent import IntentClassifier  # noqa: E402
from router.policy import PolicyEngine  # noqa: E402
from router.cache.semantic import SemanticCache  # noqa: E402

# How much worse each error type is than a plain misroute. A sensitive prompt
# escaping to a cloud provider is the failure that ends a design partnership.
CONSEQUENCE_WEIGHTS = {
    "misroute": 1.0,
    "missed_abstention": 0.5,   # guessed when it should have abstained
    "over_abstention": 0.3,     # abstained when it could have routed
    "policy_miss": 25.0,        # failed to block or contain sensitive content
    "policy_false_positive": 2.0,
}


def load_dataset(path: Path) -> List[Dict[str, Any]]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            rows.append(json.loads(line))
    return rows


class EmbeddingCache:
    """Persists embeddings so a sweep does not re-embed on every run."""

    def __init__(self, path: Optional[Path], embedder: SemanticCache):
        self.path = path
        self.embedder = embedder
        self.data: Dict[str, List[float]] = {}
        if path and path.exists():
            self.data = json.loads(path.read_text())

    async def get(self, text: str) -> Optional[List[float]]:
        if text in self.data:
            return self.data[text]
        vec = await self.embedder.embed(text)
        if vec:
            self.data[text] = vec
        return vec

    def save(self):
        if self.path:
            self.path.write_text(json.dumps(self.data))


def confusion_matrix(results: List[Dict[str, Any]], labels: List[str]) -> str:
    counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in results:
        counts[r["expected"]][r["predicted"]] += 1

    width = max(len(l) for l in labels) + 2
    header = "actual \\ predicted".ljust(width + 8) + "".join(
        l.rjust(width) for l in labels
    )
    lines = [header, "-" * len(header)]
    for actual in labels:
        row = actual.ljust(width + 8)
        for predicted in labels:
            row += str(counts[actual][predicted]).rjust(width)
        lines.append(row)
    return "\n".join(lines)


def per_class_metrics(results: List[Dict[str, Any]], labels: List[str]) -> str:
    lines = [
        "intent".ljust(12)
        + "precision".rjust(11)
        + "recall".rjust(9)
        + "f1".rjust(8)
        + "support".rjust(9)
    ]
    for label in labels:
        tp = sum(1 for r in results if r["expected"] == label and r["predicted"] == label)
        fp = sum(1 for r in results if r["expected"] != label and r["predicted"] == label)
        fn = sum(1 for r in results if r["expected"] == label and r["predicted"] != label)
        support = tp + fn
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / support if support else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        lines.append(
            label.ljust(12)
            + f"{precision:.3f}".rjust(11)
            + f"{recall:.3f}".rjust(9)
            + f"{f1:.3f}".rjust(8)
            + str(support).rjust(9)
        )
    return "\n".join(lines)


def score(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(results)
    correct = sum(1 for r in results if r["predicted"] == r["expected"])
    abstained = sum(1 for r in results if r["abstained"])

    weighted = 0.0
    error_counts: Dict[str, int] = defaultdict(int)
    for r in results:
        for err in r["errors"]:
            error_counts[err] += 1
            weighted += CONSEQUENCE_WEIGHTS.get(err, 1.0)

    return {
        "total": total,
        "accuracy": correct / total if total else 0.0,
        "abstention_rate": abstained / total if total else 0.0,
        "errors": dict(error_counts),
        "weighted_error": round(weighted, 2),
        # The number that actually matters for a governance claim.
        "policy_misses": error_counts.get("policy_miss", 0),
    }


def evaluate_row(
    row: Dict[str, Any],
    classifier: IntentClassifier,
    policy: PolicyEngine,
    embedding: Optional[List[float]],
) -> Dict[str, Any]:
    prompt = row["prompt"]
    expected = row.get("intent", "general")
    result = classifier.classify(prompt, embedding)
    verdict = policy.evaluate(prompt)

    errors: List[str] = []

    expected_policy = row.get("expect_policy")
    if expected_policy:
        if verdict.action.value != expected_policy:
            # Under-enforcing is the dangerous direction; over-enforcing is
            # merely annoying. They are counted separately.
            severity = {"block": 3, "local_only": 2, "redact": 1, "allow": 0}
            if severity.get(verdict.action.value, 0) < severity.get(expected_policy, 0):
                errors.append("policy_miss")
            else:
                errors.append("policy_false_positive")
    elif verdict.action.value != "allow":
        errors.append("policy_false_positive")

    if result.intent != expected:
        if result.abstained and expected != "general":
            errors.append("over_abstention")
        else:
            errors.append("misroute")
    elif row.get("ambiguous") and not result.abstained and expected == "general":
        errors.append("missed_abstention")

    return {
        "prompt": prompt,
        "expected": expected,
        "predicted": result.intent,
        "confidence": round(result.confidence, 4),
        "margin": round(result.margin, 4),
        "method": result.method,
        "abstained": result.abstained,
        "policy_action": verdict.action.value,
        "expected_policy": expected_policy,
        "errors": errors,
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "config" / "gateway.yaml"))
    parser.add_argument("--dataset", default=str(Path(__file__).parent / "dataset.jsonl"))
    parser.add_argument(
        "--embeddings",
        default=str(Path(__file__).parent / ".embeddings.json"),
        help="Embedding cache path; avoids re-embedding on repeat runs",
    )
    parser.add_argument("--sweep", action="store_true", help="Sweep margin thresholds")
    parser.add_argument("--rules-only", action="store_true", help="Skip embeddings")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    parser.add_argument("--fail-on-policy-miss", action="store_true")
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.config).read_text())
    dataset = load_dataset(Path(args.dataset))
    classifier = IntentClassifier.from_config(config)
    policy = PolicyEngine.from_config(config)

    embeddings: Dict[str, Optional[List[float]]] = {}
    if not args.rules_only:
        semantic = SemanticCache.from_config(config)
        cache = EmbeddingCache(Path(args.embeddings), semantic)

        probe = await cache.get("connectivity probe")
        if probe is None:
            print(
                "[eval] no embedder reachable "
                f"(OLLAMA_BASE_URL={semantic.ollama_base_url}); "
                "falling back to rules-only mode\n",
                file=sys.stderr,
            )
            args.rules_only = True
        else:
            indexed = await classifier.build_index(cache.get)
            for row in dataset:
                embeddings[row["prompt"]] = await cache.get(row["prompt"])
            cache.save()
            print(f"[eval] indexed {indexed} examples across {len(classifier.index)} intents")
        await semantic.close()

    labels = sorted({row.get("intent", "general") for row in dataset})

    def run(margin: float, min_sim: float) -> List[Dict[str, Any]]:
        classifier.config.margin_threshold = margin
        classifier.config.min_similarity = min_sim
        return [
            evaluate_row(row, classifier, policy, embeddings.get(row["prompt"]))
            for row in dataset
        ]

    if args.sweep:
        if args.rules_only:
            # Both thresholds gate the k-NN path only, so every row would be
            # identical and look like the knobs do nothing.
            print(
                "\n[eval] rules-only mode: margin and min_similarity gate the "
                "k-NN path, which is inactive.\n        Start an embedder to "
                "get a meaningful sweep.",
                file=sys.stderr,
            )
        print("\nmargin   min_sim   accuracy   abstain   weighted_err   policy_miss")
        print("-" * 68)
        for margin in (0.0, 0.01, 0.02, 0.04, 0.06, 0.10):
            for min_sim in (0.35, 0.45, 0.55):
                s = score(run(margin, min_sim))
                print(
                    f"{margin:<9.2f}{min_sim:<10.2f}{s['accuracy']:<11.3f}"
                    f"{s['abstention_rate']:<10.3f}{s['weighted_error']:<15.2f}"
                    f"{s['policy_misses']}"
                )
        return 0

    results = run(
        classifier.config.margin_threshold, classifier.config.min_similarity
    )
    summary = score(results)

    if args.json:
        print(json.dumps({"summary": summary, "results": results}, indent=2))
    else:
        mode = "rules-only" if args.rules_only else "hybrid (rules + k-NN)"
        print(f"\nKubeMind intent evaluation  [{mode}]")
        print("=" * 68)
        print(f"examples          {summary['total']}")
        print(f"accuracy          {summary['accuracy']:.3f}")
        print(f"abstention rate   {summary['abstention_rate']:.3f}")
        print(f"weighted error    {summary['weighted_error']}")
        print(f"policy misses     {summary['policy_misses']}   <- must be 0")
        print("\nerrors by type")
        for name, count in sorted(summary["errors"].items()):
            print(f"  {name:<24}{count:>4}   (weight {CONSEQUENCE_WEIGHTS.get(name, 1.0)})")
        print("\n" + per_class_metrics(results, labels))
        print("\n" + confusion_matrix(results, labels))

        wrong = [r for r in results if r["errors"]]
        if wrong:
            print(f"\n{len(wrong)} example(s) with errors:")
            for r in wrong[:15]:
                print(
                    f"  [{','.join(r['errors'])}] {r['expected']} -> {r['predicted']} "
                    f"(conf {r['confidence']:.2f}) {r['prompt'][:60]}"
                )

    if args.fail_on_policy_miss and summary["policy_misses"]:
        print("\nFAIL: policy misses present", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
