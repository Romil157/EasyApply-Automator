"""Unit tests for SDUI navigation flow, progressive circuit breaker, and search loop improvements."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from easy_apply_automator.domain.models import AppConfig
from easy_apply_automator.infra.human_simulation import AdaptiveCircuitBreaker
from easy_apply_automator.services._submit_flow import SubmitFlowMixin


class DummySubmitFlow(SubmitFlowMixin):
    """Test stub for SubmitFlowMixin."""

    def __init__(self, current_url: str = "", find_elements_return=None):
        self.bot = MagicMock()
        self.bot.browser.current_url = current_url
        self.bot.browser.find_elements.return_value = find_elements_return or []
        self.bot.current_job_id = "4456864917"
        self.bot.locator = {}


class TestSDUIApplyPageDetection:
    """Tests for _is_sdui_apply_page and SDUI modal handling."""

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://www.linkedin.com/jobs/view/4456864917/apply/?openSDUIApplyFlow=true", True),
            ("https://www.linkedin.com/jobs/view/12345/apply/", True),
            ("https://www.linkedin.com/jobs/view/4456864917/", False),
            ("https://www.linkedin.com/feed/", False),
            ("https://www.example.com/apply/?openSDUIApplyFlow=true", True),
        ],
    )
    def test_is_sdui_apply_page(self, url: str, expected: bool) -> None:
        flow = DummySubmitFlow(current_url=url)
        assert flow._is_sdui_apply_page() is expected

    def test_wait_for_apply_flow_ready_detects_sdui(self) -> None:
        flow = DummySubmitFlow(
            current_url="https://www.linkedin.com/jobs/view/4456864917/apply/?openSDUIApplyFlow=true"
        )
        mock_element = MagicMock()
        mock_element.is_displayed.return_value = True
        flow.bot.browser.find_elements.return_value = [mock_element]

        ready, mode = flow.wait_for_apply_flow_ready(timeout_seconds=0.2)
        assert ready is True
        assert mode in ("sdui_page", "modal", "controls")


class TestAdaptiveCircuitBreakerEscalation:
    """Tests for progressive cooldown escalation in AdaptiveCircuitBreaker."""

    def test_cooldown_escalation(self) -> None:
        cb = AdaptiveCircuitBreaker(
            failure_threshold=3,
            cooldown_seconds=60.0,
            escalation_factor=2.0,
            max_cooldown_seconds=300.0,
        )
        assert cb.cooldown_seconds == 60.0

        # Trigger first cooldown
        cb.record_failure()
        cb.record_failure()
        tripped = cb.record_failure()
        assert tripped is True
        assert cb.total_cooldowns == 1
        assert cb.cooldown_seconds == 60.0

        # Trigger second cooldown - should escalate (60 * 2.0^1 = 120)
        cb.record_failure()
        cb.record_failure()
        tripped = cb.record_failure()
        assert tripped is True
        assert cb.total_cooldowns == 2
        assert cb.cooldown_seconds == 120.0

        # Trigger third cooldown - should escalate (60 * 2.0^2 = 240)
        cb.record_failure()
        cb.record_failure()
        tripped = cb.record_failure()
        assert tripped is True
        assert cb.total_cooldowns == 3
        assert cb.cooldown_seconds == 240.0

        # Success resets consecutive failures and gradual recovery after 3 successes
        cb.record_success()
        cb.record_success()
        cb.record_success()
        assert cb.total_cooldowns == 2
        assert cb.cooldown_seconds == 120.0


class TestExperienceLevelDirectPassThrough:
    """Tests that AppConfig passes experience_level values directly without legacy remapping."""

    def test_experience_level_not_remapped(self) -> None:
        raw_params = {
            "positions": ["Python Developer"],
            "locations": ["Remote"],
            "experience_level": [1, 2],
        }
        config = AppConfig.from_dict(raw_params, results_filename="results/test.json")
        assert config.experience_level == [1, 2]

    def test_experience_level_internship_only(self) -> None:
        raw_params = {
            "positions": ["Software Intern"],
            "locations": ["Mumbai"],
            "experience_level": [1],
        }
        config = AppConfig.from_dict(raw_params, results_filename="results/test.json")
        assert config.experience_level == [1]


class TestSDUILinkFallbackAndValidation:
    """Tests for link-based navigation fallback and form recovery."""

    def test_click_easy_apply_direct_navigation_fallback(self) -> None:
        from easy_apply_automator.app.orchestrator import LinkedInEasyApplyOrchestrator

        bot = LinkedInEasyApplyOrchestrator.__new__(LinkedInEasyApplyOrchestrator)
        browser = MagicMock()
        browser.current_url = "https://www.linkedin.com/jobs/view/4459488338/"
        browser.window_handles = ["handle1"]
        bot.browser = browser

        apply_link = MagicMock()
        apply_link.tag_name = "a"
        apply_link.get_attribute.return_value = "https://www.linkedin.com/jobs/view/4459488338/apply/?openSDUIApplyFlow=true"

        apply_flow = MagicMock()
        apply_flow.has_apply_controls.return_value = False
        apply_flow.find_easy_apply_modal.return_value = None
        bot.apply_flow = apply_flow
        bot.load_page = MagicMock()

        bot._click_easy_apply(apply_link)
        browser.get.assert_called_with("https://www.linkedin.com/jobs/view/4459488338/apply/?openSDUIApplyFlow=true")

    def test_find_easy_apply_modal_ignores_job_details(self) -> None:
        flow = DummySubmitFlow(current_url="https://www.linkedin.com/jobs/view/4459488338/")
        job_details_mock = MagicMock()
        job_details_mock.is_displayed.return_value = True
        job_details_mock.get_attribute.return_value = "JobDetails"

        flow.bot.browser.find_elements.return_value = [job_details_mock]
        found = flow.find_easy_apply_modal()
        assert found is None

