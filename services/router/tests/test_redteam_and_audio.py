"""Unit tests for Automated Red-Teaming Simulator and Audio Speech Privacy Engine."""

from eval.red_team import RedTeamHarness
from kubemind_policy.audio import AudioPrivacyEngine


def test_red_team_adversarial_benchmark():
    harness = RedTeamHarness()
    results = harness.run_benchmark(min_block_score=0.30)

    assert results.total_vectors >= 7
    # Zero attack vector bypasses allowed
    assert results.passed_vectors == results.total_vectors
    assert results.defensive_coverage_pct == 100.0


def test_audio_speech_transcript_redaction():
    engine = AudioPrivacyEngine()

    transcript = "Doctor John Doe called regarding patient Mary Smith at phone number 555-019-2834."
    redacted, result = engine.redact_speech_request(
        audio_bytes_or_b64="RIFF....WAVE",
        simulated_transcript=transcript,
        duration_sec=3.5,
    )

    assert result.is_modified is True
    assert "John Doe" not in redacted
    assert "555-019-2834" not in redacted
    assert len(result.token_map) > 0
    assert "phone" in result.detectors_fired
