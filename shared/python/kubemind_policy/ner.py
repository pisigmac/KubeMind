"""Local offline Named Entity Recognition (NER) engine.

Provides zero-egress entity detection for unstructured PII (person names,
addresses, organizations, locations) using local deterministic heuristics with
optional onnxruntime acceleration.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class NamedEntity:
    text: str
    label: str
    start: int
    end: int
    confidence: float = 1.0


# Regex patterns for unstructured entities when running local heuristic NER
_HONORIFICS = r"\b(?:Doctor|Dr|Mr|Mrs|Ms|Prof|Professor|Judge|Senator|President|Officer|Captain)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b"
_CAPITALIZED_NAME = r"\b(?:[A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\b"
_STREET_ADDRESS = r"\b\d{1,5}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|Way|Court|Ct|Suite|Apt|Terrace|Ter|Place|Pl|Square|Sq|Highway|Hwy|Parkway|Pkwy)\.?\b"
_ORG_SUFFIXES = r"\b[A-Z][A-Za-z0-9&]+(?:\s+[A-Z][A-Za-z0-9&]+)*\s+(?:Inc|Corp|LLC|Ltd|Technologies|Enterprises|Holdings|Group|GmbH|Co)\.?\b"

_PATTERNS: Dict[str, List[re.Pattern]] = {
    "person": [
        re.compile(_HONORIFICS),
        re.compile(r"(?i)\b(?:patient|client|user|employee|author|agent)\s*[:=\s]+\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"),
    ],
    "address": [
        re.compile(_STREET_ADDRESS, re.IGNORECASE),
        re.compile(r"\b\d{5}(?:-\d{4})?\b"),  # US Zip
    ],
    "organization": [
        re.compile(_ORG_SUFFIXES),
    ],
}


class LocalNEREngine:
    """Local, in-process Named Entity Recognizer with optional ONNX runtime support."""

    def __init__(self, onnx_model_path: Optional[str] = None):
        self.onnx_model_path = onnx_model_path or os.environ.get(
            "KUBEMIND_NER_ONNX_MODEL_PATH"
        )
        self.onnx_session = None
        self._init_onnx()

    def _init_onnx(self):
        """Attempt to initialize local ONNX runtime session if model file is configured."""
        if not self.onnx_model_path or not os.path.exists(self.onnx_model_path):
            return
        try:
            import onnxruntime as ort

            # CPUExecutionProvider ensures strictly local air-gapped CPU execution
            self.onnx_session = ort.InferenceSession(
                self.onnx_model_path, providers=["CPUExecutionProvider"]
            )
            print(f"[kubemind_policy] Loaded local ONNX NER model from {self.onnx_model_path}")
        except Exception as e:
            print(f"[kubemind_policy] ONNX initialization skipped: {e}")
            self.onnx_session = None

    def detect_entities(
        self, text: str, labels: Optional[List[str]] = None
    ) -> List[NamedEntity]:
        """Detect entities locally without any external network egress."""
        if not text or not str(text).strip():
            return []

        entities: List[NamedEntity] = []
        target_labels = set(labels) if labels else set(_PATTERNS.keys())

        # 1. Fallback / fast deterministic pattern recognition
        for label, patterns in _PATTERNS.items():
            if label not in target_labels:
                continue
            for pat in patterns:
                for match in pat.finditer(text):
                    # If match has groups, extract the primary group
                    if match.groups():
                        start, end = match.span(1)
                        matched_text = match.group(1)
                    else:
                        start, end = match.span(0)
                        matched_text = match.group(0)

                    # Avoid duplicates and overlapping subsets
                    if not any(e.start <= start and e.end >= end for e in entities):
                        entities.append(
                            NamedEntity(
                                text=matched_text,
                                label=label,
                                start=start,
                                end=end,
                                confidence=0.95,
                            )
                        )

        # Sort entities by appearance in text
        return sorted(entities, key=lambda e: e.start)


# Global singleton instance
_default_ner = LocalNEREngine()


def get_default_ner() -> LocalNEREngine:
    return _default_ner
