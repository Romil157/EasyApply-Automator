"""Tests for ThroughputService — pure logic, no real WebDriver."""

from __future__ import annotations

from collections import deque
from unittest.mock import MagicMock, patch

from easy_apply_automator.services.throughput_service import ThroughputService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bot(
    *,
    session_started_at: float = 1_000_000.0,
    session_deadline: float = 1_000_000.0 + 3 * 3600,
    next_short_break_at: float = 0.0,
    short_break_min_seconds: int = 5,
    short_break_max_seconds: int = 10,
    short_break_every_min_minutes: int = 1,
    short_break_every_max_minutes: int = 2,
    throughput_window_seconds: int = 1800,
) -> MagicMock:
    bot = MagicMock()
    bot.session_started_at = session_started_at
    bot.session_deadline = session_deadline
    bot.next_short_break_at = next_short_break_at
    bot.short_break_min_seconds = short_break_min_seconds
    bot.short_break_max_seconds = short_break_max_seconds
    bot.short_break_every_min_minutes = short_break_every_min_minutes
    bot.short_break_every_max_minutes = short_break_every_max_minutes
    bot.throughput_window_seconds = throughput_window_seconds
    bot.session_jobs_processed = 0
    bot.session_jobs_submitted = 0
    bot.session_jobs_attempted = 0
    bot.session_jobs_failed_attempts = 0
    bot.session_jobs_failed_medical = 0
    bot.submitted_timestamps = deque(maxlen=1000)
    return bot


def _make_service(bot: MagicMock) -> ThroughputService:
    svc = ThroughputService.__new__(ThroughputService)
    svc.bot = bot
    return svc


# ---------------------------------------------------------------------------
# schedule_next_short_break
# ---------------------------------------------------------------------------


class TestScheduleNextShortBreak:
    def test_sets_next_break_in_the_future(self):
        bot = _make_bot()
        svc = _make_service(bot)
        with patch("time.time", return_value=1_000_000.0):
            svc.schedule_next_short_break()
        # Should be >= now + 1 minute
        assert bot.next_short_break_at >= 1_000_000.0 + 60

    def test_uses_configured_interval_bounds(self):
        bot = _make_bot(short_break_every_min_minutes=5, short_break_every_max_minutes=5)
        svc = _make_service(bot)
        with patch("time.time", return_value=0.0):
            svc.schedule_next_short_break()
        # Exactly 5 minutes in the future (both min and max are 5)
        assert bot.next_short_break_at == 5 * 60


# ---------------------------------------------------------------------------
# maybe_take_short_break
# ---------------------------------------------------------------------------


class TestMaybeTakeShortBreak:
    def test_no_break_when_not_due(self):
        """Break is not due yet; time.sleep should not be called."""
        bot = _make_bot(next_short_break_at=1_000_000.0 + 999)
        svc = _make_service(bot)
        with patch("time.time", return_value=1_000_000.0), patch("time.sleep") as mock_sleep:
            svc.maybe_take_short_break("test")
        mock_sleep.assert_not_called()

    def test_schedules_break_when_next_at_is_zero(self):
        """next_short_break_at=0 should call schedule (not sleep) and return."""
        bot = _make_bot(next_short_break_at=0.0)
        svc = _make_service(bot)
        with patch("time.time", return_value=1_000_000.0), patch("time.sleep") as mock_sleep:
            svc.maybe_take_short_break("test")
        mock_sleep.assert_not_called()
        # After scheduling, next_short_break_at should be > 0
        assert bot.next_short_break_at > 0

    def test_skips_break_when_session_nearly_over(self):
        """With < 45 seconds remaining, no break should be taken."""
        now = 1_000_000.0
        bot = _make_bot(
            next_short_break_at=now - 1,  # overdue
            session_deadline=now + 30,  # only 30 s left
        )
        svc = _make_service(bot)
        with patch("time.time", return_value=now), patch("time.sleep") as mock_sleep:
            svc.maybe_take_short_break("test")
        mock_sleep.assert_not_called()

    def test_takes_break_when_due_and_time_remaining(self):
        """When a break is overdue and there's enough session time, sleep is called."""
        now = 1_000_000.0
        bot = _make_bot(
            next_short_break_at=now - 1,  # overdue
            session_deadline=now + 3600,  # plenty of time left
            short_break_min_seconds=15,
            short_break_max_seconds=15,  # deterministic 15s break
        )
        svc = _make_service(bot)
        with patch("time.time", return_value=now), patch("time.sleep") as mock_sleep:
            svc.maybe_take_short_break("test")
        mock_sleep.assert_called_once()
        sleep_duration = mock_sleep.call_args[0][0]
        assert sleep_duration >= 15


# ---------------------------------------------------------------------------
# update_session_throughput
# ---------------------------------------------------------------------------


class TestUpdateSessionThroughput:
    def test_no_op_when_session_not_started(self):
        bot = _make_bot(session_started_at=0.0)
        svc = _make_service(bot)
        svc.update_session_throughput(reason="submitted", attempted=True, result=True)
        assert bot.session_jobs_processed == 0

    def test_increments_jobs_processed(self):
        bot = _make_bot()
        svc = _make_service(bot)
        with patch("time.time", return_value=1_000_060.0):  # 1 minute into session
            svc.update_session_throughput(reason="submitted", attempted=True, result=True)
        assert bot.session_jobs_processed == 1

    def test_increments_submitted_on_success(self):
        bot = _make_bot()
        svc = _make_service(bot)
        with patch("time.time", return_value=1_000_060.0):
            svc.update_session_throughput(reason="submitted", attempted=True, result=True)
        assert bot.session_jobs_submitted == 1

    def test_does_not_increment_submitted_on_failure(self):
        bot = _make_bot()
        svc = _make_service(bot)
        with patch("time.time", return_value=1_000_060.0):
            svc.update_session_throughput(reason="apply_flow_failed", attempted=True, result=False)
        assert bot.session_jobs_submitted == 0
        assert bot.session_jobs_failed_attempts == 1

    def test_increments_medical_failed(self):
        bot = _make_bot()
        svc = _make_service(bot)
        with patch("time.time", return_value=1_000_060.0):
            svc.update_session_throughput(
                reason="medical_related_title", attempted=True, result=False
            )
        assert bot.session_jobs_failed_medical == 1

    def test_non_attempted_does_not_count_as_failed_attempt(self):
        bot = _make_bot()
        svc = _make_service(bot)
        with patch("time.time", return_value=1_000_060.0):
            svc.update_session_throughput(
                reason="no_easy_apply_button", attempted=False, result=False
            )
        assert bot.session_jobs_attempted == 0
        assert bot.session_jobs_failed_attempts == 0
        assert bot.session_jobs_processed == 1

    def test_submitted_timestamp_appended_on_success(self):
        bot = _make_bot()
        svc = _make_service(bot)
        now = 1_000_060.0
        with patch("time.time", return_value=now):
            svc.update_session_throughput(reason="submitted", attempted=True, result=True)
        assert now in bot.submitted_timestamps

    def test_multiple_submissions_accumulate(self):
        bot = _make_bot()
        svc = _make_service(bot)
        for i in range(5):
            with patch("time.time", return_value=1_000_060.0 + i * 10):
                svc.update_session_throughput(reason="submitted", attempted=True, result=True)
        assert bot.session_jobs_submitted == 5
        assert bot.session_jobs_processed == 5

    def test_old_timestamps_pruned_from_window(self):
        """Timestamps older than the throughput window should be removed."""
        bot = _make_bot(throughput_window_seconds=60)
        svc = _make_service(bot)
        # Add an old timestamp (2 minutes ago)
        bot.submitted_timestamps.append(1_000_000.0 - 120)
        now = 1_000_000.0 + 60.0  # 60 seconds into session
        with patch("time.time", return_value=now):
            svc.update_session_throughput(reason="submitted", attempted=True, result=True)
        # The old timestamp should have been pruned
        assert 1_000_000.0 - 120 not in bot.submitted_timestamps
