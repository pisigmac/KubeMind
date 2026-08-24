#!/usr/bin/env python3
"""Train a logistic regression head over frozen embeddings.

Ships only if it beats the k-NN baseline on the held-out harness under the
same consequence-weighted error the evaluation uses. A model that is 1%
better on average accuracy while making more of the expensive mistakes is
not better, and this trainer refuses to write one.

Usage::

    python eval/train_linear_head.py
    python eval/train_linear_head.py --out models/linear_head.json --force
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT.parents[1] / "shared" / "python"))

import yaml  # noqa: E402

from router.cache.semantic import SemanticCache  # noqa: E402
from router.intent import IntentClassifier  # noqa: E402
from router.linear_head import LinearHead  # noqa: E402
from router.policy import PolicyEngine  # noqa: E402

# Reuse the same consequence weights as the eval harness.
sys.path.insert(0, str(Path(__file__).parent))
from run_eval import (  # noqa: E402
    CONSEQUENCE_WEIGHTS,
    EmbeddingCache,
    evaluate_row,
    load_dataset,
    score,
)


def _softmax(logits: List[float]) -> List[float]:
    top = max(logits)
    exps = [math.exp(v - top) for v in logits]
    denom = sum(exps) or 1.0
    return [e / denom for e in exps]


def train(
    samples: List[Tuple[List[float], str]],
    labels: List[str],
    *,
    epochs: int = 80,
    lr: float = 0.5,
    l2: float = 1e-3,
    seed: int = 7,
) -> LinearHead:
    """Plain SGD multinomial logistic regression. No numpy required."""
    rng = random.Random(seed)
    n_features = len(samples[0][0])
    label_to_i = {l: i for i, l in enumerate(labels)}
    weights = [[rng.uniform(-0.01, 0.01) for _ in range(n_features)] for _ in labels]
    bias = [0.0 for _ in labels]

    indexed = [(x, label_to_i[y]) for x, y in samples if y in label_to_i]
    for _ in range(epochs):
        rng.shuffle(indexed)
        for x, yi in indexed:
            logits = []
            for row, b in zip(weights, bias):
                total = b
                for w, xv in zip(row, x):
                    total += w * xv
                logits.append(total)
            probs = _softmax(logits)
            for j in range(len(labels)):
                err = probs[j] - (1.0 if j == yi else 0.0)
                bias[j] -= lr * (err + l2 * bias[j])
                for d in range(n_features):
                    weights[j][d] -= lr * (err * x[d] + l2 * weights[j][d])

    return LinearHead(
        labels=labels,
        weights=weights,
        bias=bias,
        trained_at=datetime.now(timezone.utc).isoformat(),
    )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "config" / "gateway.yaml"))
    parser.add_argument("--dataset", default=str(Path(__file__).parent / "dataset.jsonl"))
    parser.add_argument(
        "--embeddings", default=str(Path(__file__).parent / ".embeddings.json")
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "models" / "linear_head.json"),
        help="Where to write the trained head if it wins",
    )
    parser.add_argument(
        "--holdout",
        type=float,
        default=0.35,
        help="Fraction held out for comparison against k-NN",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Write the model even if it does not beat k-NN (for debugging)",
    )
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.config).read_text())
    dataset = load_dataset(Path(args.dataset))
    classifier = IntentClassifier.from_config(config)
    policy = PolicyEngine.from_config(config)

    semantic = SemanticCache.from_config(config)
    cache = EmbeddingCache(Path(args.embeddings), semantic)
    probe = await cache.get("connectivity probe")
    if probe is None:
        print("[train] no embedder reachable; cannot train", file=sys.stderr)
        await semantic.close()
        return 2

    await classifier.build_index(cache.get)
    embeddings: Dict[str, List[float]] = {}
    for row in dataset:
        vec = await cache.get(row["prompt"])
        if vec:
            embeddings[row["prompt"]] = vec
    cache.save()
    await semantic.close()

    # Deterministic split; never train on the rows we score against.
    pool = sorted(
        (r for r in dataset if r["prompt"] in embeddings and not r.get("expect_policy")),
        key=lambda r: hashlib.sha256(r["prompt"].encode()).hexdigest(),
    )
    n_hold = max(1, int(len(pool) * args.holdout))
    holdout, train_rows = pool[:n_hold], pool[n_hold:]
    if len(train_rows) < 5:
        print("[train] not enough labelled rows to train", file=sys.stderr)
        return 2

    labels = sorted({r.get("intent", "general") for r in train_rows + holdout})
    # Keep the decoy out of the head: it is an abstention sink for k-NN, not a
    # class we want the linear model to compete for.
    labels = [l for l in labels if l != "_background"]

    train_samples = [
        (embeddings[r["prompt"]], r.get("intent", "general")) for r in train_rows
    ]
    head = train(train_samples, labels)
    head.embedding_model = semantic.embedding_model
    head.embedding_prefix = semantic.embedding_prefix

    # Score both systems on the holdout with the same harness.
    knn_results = [
        evaluate_row(r, classifier, policy, embeddings[r["prompt"]]) for r in holdout
    ]
    knn_summary = score(knn_results)

    classifier.linear_head = head
    linear_results = [
        evaluate_row(r, classifier, policy, embeddings[r["prompt"]]) for r in holdout
    ]
    linear_summary = score(linear_results)

    print("\nLinear head vs k-NN (held-out)")
    print("=" * 56)
    print(f"{'':16}{'k-NN':>12}{'linear':>12}")
    print(
        f"{'accuracy':16}{knn_summary['accuracy']:>12.3f}{linear_summary['accuracy']:>12.3f}"
    )
    print(
        f"{'weighted_err':16}{knn_summary['weighted_error']:>12.2f}"
        f"{linear_summary['weighted_error']:>12.2f}"
    )
    print(
        f"{'policy_miss':16}{knn_summary['policy_misses']:>12}"
        f"{linear_summary['policy_misses']:>12}"
    )
    print(f"train={len(train_rows)}  holdout={len(holdout)}  labels={labels}")

    # Win condition: lower weighted error, no increase in policy misses, and
    # at least as good accuracy. Accuracy alone is not enough.
    wins = (
        linear_summary["weighted_error"] < knn_summary["weighted_error"]
        and linear_summary["policy_misses"] <= knn_summary["policy_misses"]
        and linear_summary["accuracy"] >= knn_summary["accuracy"] - 1e-9
    )

    head.metrics = {
        "knn_accuracy": knn_summary["accuracy"],
        "linear_accuracy": linear_summary["accuracy"],
        "knn_weighted_error": knn_summary["weighted_error"],
        "linear_weighted_error": linear_summary["weighted_error"],
        "holdout_size": float(len(holdout)),
        "beats_knn": float(wins),
    }

    if wins or args.force:
        head.save(args.out)
        print(f"\nWrote {args.out}" + (" (forced)" if not wins else " (beats k-NN)"))
        print(
            "Point routing.classifier.linear_head_path at this file in gateway.yaml "
            "to activate it."
        )
        return 0

    print(
        "\nRefusing to ship: linear head does not beat k-NN on consequence-weighted "
        "error. Pass --force to write anyway for inspection."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
