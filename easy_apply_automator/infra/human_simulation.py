"""Human simulation and anti-detection algorithms for natural browser automation.

Provides cubic Bézier mouse movement curves, natural keystroke jitter, smooth scrolling,
realistic job reading pauses, and adaptive cooldown circuit breakers.
"""

from __future__ import annotations

import math
import random
import time
from typing import Any

from easy_apply_automator.observability.logger import log


def calculate_bezier_curve(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    num_points: int = 20,
) -> list[tuple[float, float]]:
    """Calculates points along a cubic Bézier curve defined by control points p0, p1, p2, p3."""
    points = []
    for i in range(num_points + 1):
        t = i / float(num_points)
        # Cubic Bézier formula: B(t) = (1-t)^3*P0 + 3(1-t)^2*t*P1 + 3(1-t)*t^2*P2 + t^3*P3
        x = (
            ((1 - t) ** 3) * p0[0]
            + 3 * ((1 - t) ** 2) * t * p1[0]
            + 3 * (1 - t) * (t**2) * p2[0]
            + (t**3) * p3[0]
        )
        y = (
            ((1 - t) ** 3) * p0[1]
            + 3 * ((1 - t) ** 2) * t * p1[1]
            + 3 * (1 - t) * (t**2) * p2[1]
            + (t**3) * p3[1]
        )
        points.append((round(x, 2), round(y, 2)))
    return points


def generate_human_mouse_path(
    start: tuple[float, float],
    end: tuple[float, float],
    num_points: int = 15,
) -> list[tuple[float, float]]:
    """Generates a realistic human-like mouse curve between start and end coordinates."""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dist = math.hypot(dx, dy)

    if dist < 5.0:
        return [start, end]

    # Generate realistic intermediate control points with slight natural overshoot / curve
    deviation = min(60.0, max(15.0, dist * 0.2))
    p1 = (
        start[0] + dx * random.uniform(0.2, 0.4) + random.uniform(-deviation, deviation),
        start[1] + dy * random.uniform(0.2, 0.4) + random.uniform(-deviation, deviation),
    )
    p2 = (
        start[0] + dx * random.uniform(0.6, 0.8) + random.uniform(-deviation, deviation),
        start[1] + dy * random.uniform(0.6, 0.8) + random.uniform(-deviation, deviation),
    )

    return calculate_bezier_curve(start, p1, p2, end, num_points=num_points)


def human_type_with_jitter(
    element: Any,
    text: str,
    min_delay: float = 0.02,
    max_delay: float = 0.065,
) -> None:
    """Sends keystrokes with randomized delays and micro-pauses at spaces/punctuation."""
    for char in text:
        element.send_keys(char)
        delay = random.uniform(min_delay, max_delay)
        if char in " .,-_/@":
            delay += random.uniform(0.04, 0.09)
        time.sleep(delay)


def smooth_scroll_to(
    browser: Any,
    target_y: int,
    step_size: int = 200,
    pause_sec: float = 0.02,
) -> None:
    """Scrolls smoothly to target_y in incremental steps to mimic mouse-wheel actions."""
    try:
        current_y = int(browser.execute_script("return window.pageYOffset || document.documentElement.scrollTop || 0;"))
        if current_y == target_y:
            return

        direction = 1 if target_y > current_y else -1
        while (direction == 1 and current_y < target_y) or (direction == -1 and current_y > target_y):
            next_y = current_y + (direction * random.randint(step_size - 40, step_size + 40))
            if (direction == 1 and next_y > target_y) or (direction == -1 and next_y < target_y):
                next_y = target_y
            browser.execute_script(f"window.scrollTo(0, {next_y});")
            current_y = next_y
            time.sleep(pause_sec * random.uniform(0.8, 1.3))
    except Exception as exc:
        log.debug(f"Smooth scroll fallback to direct scrollTo: {exc}")
        try:
            browser.execute_script(f"window.scrollTo(0, {target_y});")
        except Exception:
            pass


def reading_pause(min_seconds: float = 1.2, max_seconds: float = 2.8) -> None:
    """Performs a randomized pause simulating human reading of a job posting."""
    pause = random.uniform(min_seconds, max_seconds)
    time.sleep(pause)


class AdaptiveCircuitBreaker:
    """Monitors consecutive failure bursts and triggers progressive cooldowns to prevent rate limiting."""

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: float = 60.0,
        escalation_factor: float = 1.5,
        max_cooldown_seconds: float = 300.0,
    ):
        self.failure_threshold = failure_threshold
        self.base_cooldown_seconds = cooldown_seconds
        self.escalation_factor = escalation_factor
        self.max_cooldown_seconds = max_cooldown_seconds
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.total_cooldowns = 0

    @property
    def cooldown_seconds(self) -> float:
        """Returns the calculated escalating cooldown duration."""
        factor = self.escalation_factor ** max(0, self.total_cooldowns - 1)
        return min(self.max_cooldown_seconds, self.base_cooldown_seconds * factor)

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        if self.consecutive_successes >= 3 and self.total_cooldowns > 0:
            self.total_cooldowns = max(0, self.total_cooldowns - 1)

    def record_failure(self) -> bool:
        """Records a failed attempt. Returns True if circuit tripped and cooldown is recommended."""
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        if self.consecutive_failures >= self.failure_threshold:
            self.total_cooldowns += 1
            self.consecutive_failures = 0
            return True
        return False
