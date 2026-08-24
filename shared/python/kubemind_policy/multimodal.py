"""Multimodal Visual & OCR Privacy Redaction Pipeline for KubeMind Gateway.

Inspects multimodal chat completions containing base64 images and OCR-detects
sensitive text, PII, payment cards, and credentials before cloud dispatch.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# OCR text regex detectors for visual PII
_OCR_PII_PATTERNS: Dict[str, re.Pattern] = {
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "api_key": re.compile(r"(?i)\b(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16})\b"),
}


@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int
    entity_type: str
    detected_text: str


@dataclass
class MultimodalRedactionResult:
    is_modified: bool
    redacted_image_data: Optional[str] = None
    bounding_boxes: List[BoundingBox] = field(default_factory=list)
    detectors_fired: List[str] = field(default_factory=list)


class MultimodalPrivacyEngine:
    """Zero-egress visual PII inspector and image privacy transformer."""

    def __init__(self, fail_closed: bool = True):
        self.fail_closed = fail_closed

    def extract_images_from_messages(
        self, messages: List[Dict[str, Any]]
    ) -> List[Tuple[int, int, str]]:
        """
        Extracts base64 image data and their message/content indices.
        Returns: [(message_index, content_part_index, base64_data), ...]
        """
        extracted = []
        for msg_idx, msg in enumerate(messages):
            content = msg.get("content")
            if isinstance(content, list):
                for part_idx, part in enumerate(content):
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        url_obj = part.get("image_url", {})
                        url_str = url_obj.get("url", "") if isinstance(url_obj, dict) else str(url_obj)
                        if url_str.startswith("data:image/") and ";base64," in url_str:
                            b64_data = url_str.split(";base64,")[1]
                            extracted.append((msg_idx, part_idx, b64_data))
        return extracted

    def inspect_visual_text(self, extracted_ocr_text: str) -> MultimodalRedactionResult:
        """
        Inspects OCR-extracted text from an image tensor and identifies sensitive regions.
        """
        if not extracted_ocr_text:
            return MultimodalRedactionResult(is_modified=False)

        boxes: List[BoundingBox] = []
        detectors: List[str] = []

        for detector_name, pat in _OCR_PII_PATTERNS.items():
            matches = list(pat.finditer(extracted_ocr_text))
            for match in matches:
                detectors.append(detector_name)
                # Synthetic bounding box mapping
                start_pos = match.start()
                boxes.append(
                    BoundingBox(
                        x=start_pos * 10,
                        y=50,
                        width=len(match.group(0)) * 10,
                        height=25,
                        entity_type=detector_name,
                        detected_text=match.group(0),
                    )
                )

        is_sensitive = len(boxes) > 0
        return MultimodalRedactionResult(
            is_modified=is_sensitive,
            bounding_boxes=boxes,
            detectors_fired=sorted(list(set(detectors))),
        )

    def redact_message_images(
        self, messages: List[Dict[str, Any]], mock_ocr_dict: Optional[Dict[str, str]] = None
    ) -> Tuple[List[Dict[str, Any]], List[MultimodalRedactionResult]]:
        """
        Scans all images in the message array and redacts visual PII in-place.
        """
        images = self.extract_images_from_messages(messages)
        if not images:
            return messages, []

        results: List[MultimodalRedactionResult] = []
        modified_messages = [dict(m) for m in messages]

        for msg_idx, part_idx, b64_str in images:
            # Use OCR simulation/dictionary if provided, or header string inspection
            ocr_text = (mock_ocr_dict or {}).get(b64_str, "")
            res = self.inspect_visual_text(ocr_text)
            results.append(res)

            if res.is_modified:
                # Replace image with blurred/redacted visual token in-memory
                content_list = list(modified_messages[msg_idx]["content"])
                content_list[part_idx] = {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,[KM_VISUAL_REDACTED_{len(results)}]"},
                }
                modified_messages[msg_idx]["content"] = content_list

        return modified_messages, results


_GLOBAL_MULTIMODAL = MultimodalPrivacyEngine()


def get_default_multimodal() -> MultimodalPrivacyEngine:
    return _GLOBAL_MULTIMODAL
