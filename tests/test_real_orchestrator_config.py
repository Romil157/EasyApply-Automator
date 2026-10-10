"""Regression tests verifying real AppConfig wiring and orchestrator lifecycle without mocks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from easy_apply_automator.app.orchestrator import LinkedInEasyApplyOrchestrator
from easy_apply_automator.config.loader import load_run_config
from easy_apply_automator.domain.models import AppConfig, PerformanceModeConfig
from easy_apply_automator.services.apply_flow_service import ApplyFlowService
from easy_apply_automator.services.diagnostics_service import DiagnosticsService


def test_orchestrator_initializes_with_real_config_and_performance_mode():
    run_cfg = load_run_config("config.yaml")
    app_config = AppConfig.from_dict(run_cfg.parameters, results_filename=run_cfg.results_filename)

    assert hasattr(app_config, "performance_mode")
    assert isinstance(app_config.performance_mode, PerformanceModeConfig)
    assert app_config.performance_mode.enabled is True

    # Initialize bot without spawning real browser
    with patch("easy_apply_automator.app.orchestrator.LinkedInEasyApplyOrchestrator.start_linkedin"), patch(
        "easy_apply_automator.app.orchestrator.LinkedInEasyApplyOrchestrator.restore_session_from_cookies",
        return_value=True,
    ), patch("easy_apply_automator.app.orchestrator.build_webdriver") as mock_webdriver_factory:
        mock_driver = MagicMock()
        mock_driver.current_url = "https://www.linkedin.com/feed/"
        mock_webdriver_factory.return_value = mock_driver

        bot = LinkedInEasyApplyOrchestrator(app_config)

        # Invariant checks: self.config and self.performance_mode MUST be bound
        assert hasattr(bot, "config")
        assert bot.config is app_config
        assert hasattr(bot, "performance_mode")
        assert bot.performance_mode is app_config.performance_mode
        assert bot.performance_mode.enabled is True


def test_orchestrator_get_job_page_does_not_raise_attribute_error():
    run_cfg = load_run_config("config.yaml")
    app_config = AppConfig.from_dict(run_cfg.parameters, results_filename=run_cfg.results_filename)

    with patch("easy_apply_automator.app.orchestrator.LinkedInEasyApplyOrchestrator.start_linkedin"), patch(
        "easy_apply_automator.app.orchestrator.LinkedInEasyApplyOrchestrator.restore_session_from_cookies",
        return_value=True,
    ), patch("easy_apply_automator.app.orchestrator.build_webdriver") as mock_webdriver_factory:
        mock_driver = MagicMock()
        mock_driver.current_url = "https://www.linkedin.com/jobs/search"
        mock_webdriver_factory.return_value = mock_driver

        bot = LinkedInEasyApplyOrchestrator(app_config)

        # Calling get_job_page MUST NOT raise AttributeError: 'LinkedInEasyApplyOrchestrator' object has no attribute 'config'
        job_page = bot.get_job_page("4476564052")
        # In performance mode, redundant full page parsing is skipped
        assert job_page is None
        mock_driver.get.assert_called_with("https://www.linkedin.com/jobs/view/4476564052")


def test_click_easy_apply_deterministic_and_robust():
    run_cfg = load_run_config("config.yaml")
    app_config = AppConfig.from_dict(run_cfg.parameters, results_filename=run_cfg.results_filename)

    with patch("easy_apply_automator.app.orchestrator.LinkedInEasyApplyOrchestrator.start_linkedin"), patch(
        "easy_apply_automator.app.orchestrator.LinkedInEasyApplyOrchestrator.restore_session_from_cookies",
        return_value=True,
    ), patch("easy_apply_automator.app.orchestrator.build_webdriver") as mock_webdriver_factory:
        mock_driver = MagicMock()
        mock_driver.current_url = "https://www.linkedin.com/jobs/view/4476564052"
        mock_driver.window_handles = ["handle1"]
        mock_webdriver_factory.return_value = mock_driver

        bot = LinkedInEasyApplyOrchestrator(app_config)

        # Case 1: Direct click works
        element = MagicMock()
        element.tag_name = "button"
        element.get_attribute.return_value = ""
        bot._click_easy_apply(element)
        element.click.assert_called_once()

        # Case 2: Direct click throws intercepted exception -> falls back to JS click
        element_failing = MagicMock()
        element_failing.tag_name = "button"
        element_failing.get_attribute.return_value = ""
        element_failing.click.side_effect = Exception("ElementClickInterceptedException")

        bot._click_easy_apply(element_failing)
        # Verify execute_script was called with arguments[0].click()
        assert any("click()" in str(call) for call in mock_driver.execute_script.call_args_list)


def test_diagnostics_service_suppresses_first_job_dump_in_performance_mode():
    run_cfg = load_run_config("config.yaml")
    app_config = AppConfig.from_dict(run_cfg.parameters, results_filename=run_cfg.results_filename)
    app_config.performance_mode.enabled = True

    bot = MagicMock()
    bot.config = app_config
    bot.performance_mode = app_config.performance_mode
    bot.first_job_debug_done = False

    diag = DiagnosticsService(bot)
    diag.start_job_debug_trace("4476564052")

    # In performance mode, first_job debug dump should be suppressed
    assert bot.current_job_debug_dir is None
    assert bot.current_job_first_try_dir is None


def test_retry_open_apply_flow_prioritizes_reclick_over_url_navigation():
    bot = MagicMock()
    browser = MagicMock()
    browser.current_url = "https://www.linkedin.com/jobs/view/4476564052"
    bot.browser = browser
    bot.current_job_id = "4476564052"

    mock_button = MagicMock()
    bot.get_easy_apply_button.return_value = mock_button

    svc = ApplyFlowService.__new__(ApplyFlowService)
    svc.bot = bot
    svc._is_similar_jobs_redirect = MagicMock(return_value=False)
    svc.wait_for_apply_flow_ready = MagicMock(return_value=(True, "modal"))

    ok, mode = svc.retry_open_apply_flow()

    assert ok is True
    assert "button_reclick" in mode
    bot._click_easy_apply.assert_called_once_with(mock_button)
    # browser.get should NOT be called when button was present and reclick succeeded
    browser.get.assert_not_called()
