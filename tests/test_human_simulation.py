"""Unit tests for human simulation and anti-detection routines."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from easy_apply_automator.infra.human_simulation import (
    AdaptiveCircuitBreaker,
    calculate_bezier_curve,
    generate_human_mouse_path,
    human_type_with_jitter,
    reading_pause,
    smooth_scroll_to,
)


class TestBezierCurveCalculation:
    def test_calculate_bezier_curve_endpoints_and_length(self):
        p0 = (100.0, 100.0)
        p1 = (150.0, 120.0)
        p2 = (250.0, 280.0)
        p3 = (300.0, 300.0)
        points = calculate_bezier_curve(p0, p1, p2, p3, num_points=10)

        assert len(points) == 11
        assert points[0] == p0
        assert points[-1] == p3

    def test_generate_human_mouse_path_short_distance(self):
        start = (10.0, 10.0)
        end = (12.0, 12.0)
        path = generate_human_mouse_path(start, end)
        assert len(path) == 2
        assert path[0] == start
        assert path[1] == end

    def test_generate_human_mouse_path_long_distance(self):
        start = (50.0, 50.0)
        end = (500.0, 400.0)
        path = generate_human_mouse_path(start, end, num_points=15)
        assert len(path) == 16
        assert path[0] == start
        assert path[-1] == end


class TestHumanTypingAndScrolling:
    @patch("time.sleep")
    def test_human_type_with_jitter(self, mock_sleep):
        element = MagicMock()
        text = "Hello World!"
        human_type_with_jitter(element, text, min_delay=0.001, max_delay=0.002)

        assert element.send_keys.call_count == len(text)
        assert mock_sleep.call_count == len(text)

    @patch("time.sleep")
    def test_smooth_scroll_to_increments(self, mock_sleep):
        browser = MagicMock()
        browser.execute_script.side_effect = [
            0,     # initial pageYOffset
            None,  # step 1
            None,  # step 2
            None,  # final step
        ]
        smooth_scroll_to(browser, target_y=500, step_size=200, pause_sec=0.01)
        assert browser.execute_script.call_count >= 2

    @patch("time.sleep")
    def test_reading_pause_sleeps_within_range(self, mock_sleep):
        reading_pause(min_seconds=0.1, max_seconds=0.2)
        mock_sleep.assert_called_once()
        delay = mock_sleep.call_args[0][0]
        assert 0.1 <= delay <= 0.2


class TestAdaptiveCircuitBreaker:
    def test_circuit_breaker_triggers_after_threshold(self):
        cb = AdaptiveCircuitBreaker(failure_threshold=3, cooldown_seconds=30.0)

        assert cb.record_failure() is False
        assert cb.consecutive_failures == 1

        assert cb.record_failure() is False
        assert cb.consecutive_failures == 2

        # 3rd failure trips the circuit
        assert cb.record_failure() is True
        assert cb.consecutive_failures == 0
        assert cb.total_cooldowns == 1

    def test_circuit_breaker_resets_on_success(self):
        cb = AdaptiveCircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.consecutive_failures == 2

        cb.record_success()
        assert cb.consecutive_failures == 0
