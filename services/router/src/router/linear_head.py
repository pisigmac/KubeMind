"""Optional logistic-regression head over the frozen embeddings.

k-NN is the right default: it needs no training, adapts the moment an example
is added to `gateway.yaml`, and is easy to reason about. Its weakness is that
it treats every dimension as equally informative and every example as equally
representative. With a few hundred real labels, a linear head learns which
directions in the embedding space actually separate the intents.

Runtime cost is the same order as k-NN -- one small matrix multiply against
frozen vectors, no second embedding call, no new service. Inference is written
in plain Python so the router gains no numerical dependency; training lives in
`eval/train_linear_head.py` and is offline.

**This ships only if it wins.** The trainer refuses to write a model that does
not beat the k-NN baseline on the held-out harness, using the same
consequence-weighted error the evaluation uses. A model that is 1% better on
average accuracy while making more of the expensive mistakes is not better.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence


@dataclass
class LinearHead:
    """Multinomial logistic regression: softmax(W·x + b)."""

    labels: List[str]
    weights: List[List[float]]  # [n_labels][n_features]
    bias: List[float]
    embedding_model: str = ""
    embedding_prefix: str = ""
    trained_at: str = ""
    metrics: Optional[Dict[str, float]] = None

    @property
    def n_features(self) -> int:
        return len(self.weights[0]) if self.weights else 0

    def scores(self, embedding: Sequence[float]) -> Dict[str, float]:
        """Class probabilities for one embedding.

        Returns {} on a dimension mismatch rather than raising: the caller
        falls back to k-NN, which is the safe behaviour when a stale model
        outlives the embedding model it was trained against.
        """
        if not self.weights or len(embedding) != self.n_features:
            return {}

        logits = []
        for row, b in zip(self.weights, self.bias):
            total = b
            for w, x in zip(row, embedding):
                total += w * x
            logits.append(total)

        top = max(logits)
        exps = [math.exp(v - top) for v in logits]
        denom = sum(exps) or 1.0
        return {label: e / denom for label, e in zip(self.labels, exps)}

    # ── Persistence ──────────────────────────────────────────────

    def to_dict(self) -> Dict:
        return {
            "labels": self.labels,
            "weights": self.weights,
            "bias": self.bias,
            "embedding_model": self.embedding_model,
            "embedding_prefix": self.embedding_prefix,
            "trained_at": self.trained_at,
            "metrics": self.metrics or {},
        }

    def save(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict()))

    @classmethod
    def load(cls, path: str | Path) -> Optional["LinearHead"]:
        """Load a trained head, or None if it is absent or unreadable.

        Returning None rather than raising is deliberate: a missing or corrupt
        optional model must degrade to the k-NN baseline, not stop the router
        from starting.
        """
        try:
            data = json.loads(Path(path).read_text())
            return cls(
                labels=list(data["labels"]),
                weights=[list(map(float, row)) for row in data["weights"]],
                bias=[float(b) for b in data["bias"]],
                embedding_model=data.get("embedding_model", ""),
                embedding_prefix=data.get("embedding_prefix", ""),
                trained_at=data.get("trained_at", ""),
                metrics=data.get("metrics") or {},
            )
        except Exception:
            return None

    def compatible_with(self, embedding_model: str, embedding_prefix: str) -> bool:
        """Whether this head was trained against the current embedder.

        Weights learned over one embedding space are meaningless in another,
        and the failure is silent -- confident, wrong predictions rather than
        an error. Checked explicitly for that reason.
        """
        if self.embedding_model and self.embedding_model != embedding_model:
            return False
        if self.embedding_prefix and self.embedding_prefix != embedding_prefix:
            return False
        return True
