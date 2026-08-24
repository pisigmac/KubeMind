"""Harvesting free labels from production traffic.

The two properties that matter here are what gets captured (the informative
cases, not a random sample) and what never gets captured (anything sensitive).
"""

import json

import pytest

from router.feedback import (
    REASON_ABSTENTION,
    REASON_FALLBACK,
    REASON_LOW_CONFIDENCE,
    REASON_POLICY_OVERRIDE,
    FeedbackConfig,
    FeedbackLog,
)


@pytest.fixture
def log():
    return FeedbackLog(config=FeedbackConfig(low_confidence_threshold=0.55))


async def _capture(log, prompt="why is my pod crashlooping", **kw):
    defaults = dict(
        workspace_id="acme",
        reason=REASON_LOW_CONFIDENCE,
        prompt=prompt,
        predicted_intent="log",
        confidence=0.4,
        margin=0.01,
        scores={"log": 0.6, "code": 0.59},
        profile="fast_local",
    )
    defaults.update(kw)
    return await log.capture(**defaults)


class TestCaptureSelection:
    def test_abstention_is_captured(self, log):
        assert (
            log.should_capture(abstained=True, confidence=0.9, used_fallback=False)
            == REASON_ABSTENTION
        )

    def test_fallback_is_captured(self, log):
        # The first-choice provider failed, which is evidence the profile's
        # pool ordering is wrong for this kind of prompt.
        assert (
            log.should_capture(abstained=False, confidence=0.9, used_fallback=True)
            == REASON_FALLBACK
        )

    def test_low_confidence_is_captured(self, log):
        assert (
            log.should_capture(abstained=False, confidence=0.3, used_fallback=False)
            == REASON_LOW_CONFIDENCE
        )

    def test_policy_override_is_captured(self, log):
        assert (
            log.should_capture(
                abstained=False,
                confidence=0.9,
                used_fallback=False,
                policy_action="local_only",
            )
            == REASON_POLICY_OVERRIDE
        )

    def test_confident_routine_request_is_not_captured(self, log):
        # Reviewing these teaches the classifier what it already knows.
        assert (
            log.should_capture(abstained=False, confidence=0.95, used_fallback=False)
            is None
        )

    def test_disabled_captures_nothing(self):
        log = FeedbackLog(config=FeedbackConfig(enabled=False))
        assert log.should_capture(abstained=True, confidence=0.0, used_fallback=True) is None

    def test_threshold_is_configurable(self):
        log = FeedbackLog(config=FeedbackConfig(low_confidence_threshold=0.2))
        assert (
            log.should_capture(abstained=False, confidence=0.3, used_fallback=False)
            is None
        )


class TestSensitiveContentIsNeverQueued:
    @pytest.mark.asyncio
    async def test_flagged_prompt_is_dropped(self, log):
        assert await _capture(log, sensitive=True) is None

    @pytest.mark.asyncio
    async def test_prompt_containing_pii_is_dropped(self, log):
        # Detected independently of the caller's flag, so a missed hand-off
        # upstream does not put an email address in the review queue.
        assert await _capture(log, prompt="email alice@example.com about it") is None

    @pytest.mark.asyncio
    async def test_ordinary_prompt_is_kept(self, log):
        case = await _capture(log)
        assert case is not None
        assert case.prompt == "why is my pod crashlooping"

    @pytest.mark.asyncio
    async def test_prompt_is_truncated(self):
        log = FeedbackLog(config=FeedbackConfig(max_prompt_chars=20))
        case = await _capture(log, prompt="x" * 500)
        assert len(case.prompt) <= 20


class TestQueue:
    @pytest.mark.asyncio
    async def test_captured_case_is_pending(self, log):
        await _capture(log)
        pending = await log.pending("acme")
        assert len(pending) == 1
        assert pending[0]["predicted_intent"] == "log"

    @pytest.mark.asyncio
    async def test_queue_is_scoped_to_the_workspace(self, log):
        await _capture(log, workspace_id="acme")
        await _capture(log, workspace_id="globex")
        assert len(await log.pending("acme")) == 1

    @pytest.mark.asyncio
    async def test_filter_by_reason(self, log):
        await _capture(log, reason=REASON_ABSTENTION)
        await _capture(log, reason=REASON_FALLBACK)
        assert len(await log.pending("acme", reason=REASON_FALLBACK)) == 1

    @pytest.mark.asyncio
    async def test_reviewed_cases_leave_the_pending_list(self, log):
        case = await _capture(log)
        await log.review("acme", case.case_id, "log")
        assert await log.pending("acme") == []
        assert len(await log.pending("acme", include_reviewed=True)) == 1

    @pytest.mark.asyncio
    async def test_review_of_unknown_case_returns_none(self, log):
        assert await log.review("acme", "nope", "log") is None

    @pytest.mark.asyncio
    async def test_queue_is_capped(self):
        log = FeedbackLog(config=FeedbackConfig(max_cases=5))
        for _ in range(10):
            await _capture(log)
        assert len(await log.pending("acme", limit=100)) == 5


class TestExport:
    @pytest.mark.asyncio
    async def test_only_reviewed_cases_are_exported(self, log):
        """Exporting predictions would let the classifier grade its own work."""
        reviewed = await _capture(log, prompt="reviewed one")
        await _capture(log, prompt="unreviewed one")
        await log.review("acme", reviewed.case_id, "log")

        lines = [json.loads(l) for l in (await log.export_jsonl("acme")).splitlines()]
        assert len(lines) == 1
        assert lines[0]["prompt"] == "reviewed one"
        assert lines[0]["intent"] == "log"

    @pytest.mark.asyncio
    async def test_export_matches_the_eval_dataset_shape(self, log):
        case = await _capture(log)
        await log.review("acme", case.case_id, "code")
        row = json.loads((await log.export_jsonl("acme")).splitlines()[0])
        assert set(row) == {"prompt", "intent", "source"}

    @pytest.mark.asyncio
    async def test_empty_export_is_empty(self, log):
        assert await log.export_jsonl("acme") == ""


class TestDriftSummary:
    @pytest.mark.asyncio
    async def test_disagreement_rate_is_reported(self, log):
        agree = await _capture(log, prompt="a")
        disagree = await _capture(log, prompt="b")
        await log.review("acme", agree.case_id, "log")       # matches prediction
        await log.review("acme", disagree.case_id, "code")   # does not

        summary = await log.summary("acme")
        assert summary["reviewed"] == 2
        assert summary["disagreement_rate"] == 0.5
        assert summary["confusions"] == {"log->code": 1}

    @pytest.mark.asyncio
    async def test_no_reviews_means_no_rate(self, log):
        await _capture(log)
        assert (await log.summary("acme"))["disagreement_rate"] is None

    @pytest.mark.asyncio
    async def test_live_distribution_tracks_all_traffic(self, log):
        for _ in range(3):
            log.observe("code")
        log.observe("log")
        summary = await log.summary("acme")
        assert summary["requests_observed"] == 4
        assert summary["live_intent_distribution"]["code"] == 0.75

    @pytest.mark.asyncio
    async def test_counts_by_reason(self, log):
        await _capture(log, reason=REASON_ABSTENTION)
        await _capture(log, reason=REASON_ABSTENTION)
        await _capture(log, reason=REASON_FALLBACK)
        assert (await log.summary("acme"))["by_reason"] == {
            REASON_ABSTENTION: 2,
            REASON_FALLBACK: 1,
        }


class TestConfigLoading:
    def test_defaults(self):
        cfg = FeedbackConfig.from_config({})
        assert cfg.enabled is True
        assert cfg.skip_sensitive is True

    def test_reads_the_routing_block(self):
        cfg = FeedbackConfig.from_config(
            {"routing": {"feedback": {"enabled": False, "low_confidence_threshold": 0.8}}}
        )
        assert cfg.enabled is False
        assert cfg.low_confidence_threshold == 0.8
