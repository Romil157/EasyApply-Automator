"""Centralized, instrumented browser wait utilities with telemetry for EasyApply Automator."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def wait_for_condition(
    driver: Any,
    condition_fn: Callable[[], Any],
    timeout_seconds: float = 5.0,
    poll_interval: float = 0.1,
    state_name: str = "condition",
    log_event_fn: Callable[..., Any] | None = None,
) -> Any:
    """Polls condition_fn until truthy or timeout. Emits wait telemetry events."""
    timeout_ms = int(timeout_seconds * 1000)
    start_time = time.time()

    if callable(log_event_fn):
        log_event_fn("wait_started", state=state_name, timeout_ms=timeout_ms)

    deadline = start_time + timeout_seconds
    while True:
        try:
            res = condition_fn()
            if res:
                elapsed_ms = int((time.time() - start_time) * 1000)
                if callable(log_event_fn):
                    log_event_fn(
                        "wait_completed",
                        state=state_name,
                        elapsed_ms=elapsed_ms,
                        timeout_ms=timeout_ms,
                    )
                return res
        except Exception:
            pass

        if time.time() >= deadline:
            break
        time.sleep(poll_interval)

    elapsed_ms = int((time.time() - start_time) * 1000)
    if callable(log_event_fn):
        log_event_fn(
            "wait_timeout",
            state=state_name,
            elapsed_ms=elapsed_ms,
            timeout_ms=timeout_ms,
        )
    return None


def wait_for_presence(
    driver: Any,
    by: str,
    selector: str,
    timeout_seconds: float = 5.0,
    poll_interval: float = 0.1,
    log_event_fn: Callable[..., Any] | None = None,
) -> Any:
    """Waits for presence of element with timing telemetry."""
    timeout_ms = int(timeout_seconds * 1000)
    start_time = time.time()
    state_desc = f"presence:{by}:{selector}"

    if callable(log_event_fn):
        log_event_fn("wait_started", state=state_desc, timeout_ms=timeout_ms)

    try:
        wait = WebDriverWait(driver, timeout_seconds, poll_frequency=poll_interval)
        elem = wait.until(EC.presence_of_element_located((by, selector)))
        elapsed_ms = int((time.time() - start_time) * 1000)
        if callable(log_event_fn):
            log_event_fn(
                "wait_completed",
                state=state_desc,
                elapsed_ms=elapsed_ms,
                timeout_ms=timeout_ms,
            )
        return elem
    except TimeoutException:
        elapsed_ms = int((time.time() - start_time) * 1000)
        if callable(log_event_fn):
            log_event_fn(
                "wait_timeout",
                state=state_desc,
                elapsed_ms=elapsed_ms,
                timeout_ms=timeout_ms,
            )
        return None


def wait_for_visibility(
    driver: Any,
    by: str,
    selector: str,
    timeout_seconds: float = 5.0,
    poll_interval: float = 0.1,
    log_event_fn: Callable[..., Any] | None = None,
) -> Any:
    """Waits for visibility of element with timing telemetry."""
    timeout_ms = int(timeout_seconds * 1000)
    start_time = time.time()
    state_desc = f"visibility:{by}:{selector}"

    if callable(log_event_fn):
        log_event_fn("wait_started", state=state_desc, timeout_ms=timeout_ms)

    try:
        wait = WebDriverWait(driver, timeout_seconds, poll_frequency=poll_interval)
        elem = wait.until(EC.visibility_of_element_located((by, selector)))
        elapsed_ms = int((time.time() - start_time) * 1000)
        if callable(log_event_fn):
            log_event_fn(
                "wait_completed",
                state=state_desc,
                elapsed_ms=elapsed_ms,
                timeout_ms=timeout_ms,
            )
        return elem
    except TimeoutException:
        elapsed_ms = int((time.time() - start_time) * 1000)
        if callable(log_event_fn):
            log_event_fn(
                "wait_timeout",
                state=state_desc,
                elapsed_ms=elapsed_ms,
                timeout_ms=timeout_ms,
            )
        return None


def wait_for_clickable(
    driver: Any,
    by: str,
    selector: str,
    timeout_seconds: float = 5.0,
    poll_interval: float = 0.1,
    log_event_fn: Callable[..., Any] | None = None,
) -> Any:
    """Waits for element to be clickable with timing telemetry."""
    timeout_ms = int(timeout_seconds * 1000)
    start_time = time.time()
    state_desc = f"clickable:{by}:{selector}"

    if callable(log_event_fn):
        log_event_fn("wait_started", state=state_desc, timeout_ms=timeout_ms)

    try:
        wait = WebDriverWait(driver, timeout_seconds, poll_frequency=poll_interval)
        elem = wait.until(EC.element_to_be_clickable((by, selector)))
        elapsed_ms = int((time.time() - start_time) * 1000)
        if callable(log_event_fn):
            log_event_fn(
                "wait_completed",
                state=state_desc,
                elapsed_ms=elapsed_ms,
                timeout_ms=timeout_ms,
            )
        return elem
    except TimeoutException:
        elapsed_ms = int((time.time() - start_time) * 1000)
        if callable(log_event_fn):
            log_event_fn(
                "wait_timeout",
                state=state_desc,
                elapsed_ms=elapsed_ms,
                timeout_ms=timeout_ms,
            )
        return None
