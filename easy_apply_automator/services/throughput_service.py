from __future__ import annotations

import random
import time

from easy_apply_automator.observability.logger import log

from .base import ServiceBase


class ThroughputService(ServiceBase):
    def schedule_next_short_break(self) -> None:
        interval_minutes = random.randint(
            self.bot.short_break_every_min_minutes,
            self.bot.short_break_every_max_minutes,
        )
        self.bot.next_short_break_at = time.time() + (interval_minutes * 60)

    def maybe_take_short_break(self, source: str) -> None:
        if self.bot.next_short_break_at <= 0:
            self.schedule_next_short_break()
            return
        now = time.time()
        if now < self.bot.next_short_break_at:
            return
        remaining = int(self.bot.session_deadline - now)
        if remaining <= 45:
            self.schedule_next_short_break()
            return
        requested = random.randint(
            self.bot.short_break_min_seconds, self.bot.short_break_max_seconds
        )
        pause_seconds = min(requested, max(10, remaining - 30))
        if pause_seconds < 10:
            self.schedule_next_short_break()
            return
        self.bot.log_event(
            "short_break_start",
            source=source,
            duration_seconds=pause_seconds,
            remaining_minutes=round(max(0, self.bot.session_deadline - now) / 60, 2),
        )
        log.info(f"Taking a short break for {pause_seconds}s")
        time.sleep(pause_seconds)
        self.bot.log_event(
            "short_break_end", source=source, duration_seconds=pause_seconds
        )
        self.schedule_next_short_break()

    def update_session_throughput(
        self, *, reason: str, attempted: bool, result: bool
    ) -> None:
        if self.bot.session_started_at <= 0:
            return

        now = time.time()
        self.bot.session_jobs_processed += 1
        if attempted:
            self.bot.session_jobs_attempted += 1
        if reason == "submitted" and attempted and result:
            self.bot.session_jobs_submitted += 1
            self.bot.submitted_timestamps.append(now)
        elif attempted:
            self.bot.session_jobs_failed_attempts += 1
            if reason == "medical_related_title":
                self.bot.session_jobs_failed_medical += 1

        elapsed_seconds = max(1.0, now - self.bot.session_started_at)
        elapsed_hours = elapsed_seconds / 3600.0
        processed_per_hour_total = self.bot.session_jobs_processed / elapsed_hours
        submitted_per_hour_total = self.bot.session_jobs_submitted / elapsed_hours
        success_rate_pct = (
            (self.bot.session_jobs_submitted / self.bot.session_jobs_attempted) * 100.0
            if self.bot.session_jobs_attempted > 0
            else 0.0
        )

        window_start = now - self.bot.throughput_window_seconds
        while (
            self.bot.submitted_timestamps
            and self.bot.submitted_timestamps[0] < window_start
        ):
            self.bot.submitted_timestamps.popleft()
        window_seconds = min(self.bot.throughput_window_seconds, elapsed_seconds)
        window_hours = max(1.0 / 3600.0, window_seconds / 3600.0)
        submitted_per_hour_window = len(self.bot.submitted_timestamps) / window_hours

        if elapsed_seconds < 10 * 60:
            estimated_submitted_per_hour = submitted_per_hour_total
        else:
            estimated_submitted_per_hour = (0.65 * submitted_per_hour_window) + (
                0.35 * submitted_per_hour_total
            )

        remaining_seconds = max(0.0, self.bot.session_deadline - now)
        projected_total_submitted = self.bot.session_jobs_submitted + (
            estimated_submitted_per_hour * (remaining_seconds / 3600.0)
        )

        log.info(
            "Rate estimate: "
            f"{estimated_submitted_per_hour:.1f} applied/hour "
            f"(submitted={self.bot.session_jobs_submitted}, failed={self.bot.session_jobs_failed_attempts}, "
            f"medical_failed={self.bot.session_jobs_failed_medical}, "
            f"success={success_rate_pct:.1f}%, elapsed={elapsed_seconds / 60:.1f}m, "
            f"projected_total={projected_total_submitted:.0f})"
        )
        self.bot.log_event(
            "session_rate_update",
            processed_count=self.bot.session_jobs_processed,
            attempted_count=self.bot.session_jobs_attempted,
            submitted_count=self.bot.session_jobs_submitted,
            failed_attempts_count=self.bot.session_jobs_failed_attempts,
            medical_failed_count=self.bot.session_jobs_failed_medical,
            success_rate_pct=round(success_rate_pct, 2),
            elapsed_minutes=round(elapsed_seconds / 60.0, 2),
            processed_per_hour=round(processed_per_hour_total, 2),
            submitted_per_hour_total=round(submitted_per_hour_total, 2),
            submitted_per_hour_window=round(submitted_per_hour_window, 2),
            submitted_per_hour_estimated=round(estimated_submitted_per_hour, 2),
            projected_total_submitted=round(projected_total_submitted, 2),
            last_reason=reason,
        )
