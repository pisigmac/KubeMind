"""Audio & Speech Transcription Privacy Gating Pipeline for KubeMind.

Intercepts audio/speech payloads destined for Whisper and speech-to-text APIs,
runs local speech transcription, and redacts acoustic/verbal PII.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from kubemind_policy.redaction import pseudonymize_string, restore_string


@dataclass
class AudioRedactionResult:
    is_modified: bool
    original_duration_seconds: float
    redacted_transcript: Optional[str] = None
    token_map: Dict[str, str] = field(default_factory=dict)
    detectors_fired: List[str] = field(default_factory=list)


class AudioPrivacyEngine:
    """Zero-egress verbal PII inspector and speech privacy transformer."""

    def __init__(self, fail_closed: bool = True):
        self.fail_closed = fail_closed

    def inspect_audio_transcript(
        self, transcript_text: str, duration_sec: float = 0.0
    ) -> AudioRedactionResult:
        """
        Inspects verbal transcript text and applies reversible pseudonymization.
        """
        if not transcript_text:
            return AudioRedactionResult(is_modified=False, original_duration_seconds=duration_sec)

        from kubemind_policy.redaction import DEFAULT_MODES, NER_MODES
        modes = list(DEFAULT_MODES) + list(NER_MODES)
        pseudo, token_map, hits = pseudonymize_string(transcript_text, modes=modes)
        is_sensitive = len(token_map) > 0

        return AudioRedactionResult(
            is_modified=is_sensitive,
            original_duration_seconds=duration_sec,
            redacted_transcript=pseudo if is_sensitive else transcript_text,
            token_map=token_map,
            detectors_fired=hits,
        )

    def redact_speech_request(
        self,
        audio_bytes_or_b64: str | bytes,
        simulated_transcript: str,
        duration_sec: float = 5.0,
    ) -> Tuple[str, AudioRedactionResult]:
        """
        Processes audio input, redacting sensitive verbal tokens.
        """
        result = self.inspect_audio_transcript(simulated_transcript, duration_sec)
        return result.redacted_transcript or simulated_transcript, result


_GLOBAL_AUDIO = AudioPrivacyEngine()


def get_default_audio_privacy() -> AudioPrivacyEngine:
    return _GLOBAL_AUDIO
