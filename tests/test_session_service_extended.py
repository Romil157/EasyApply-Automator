"""Extended tests for SessionService logic."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest

from easy_apply_automator.services.session_service import SessionService


@pytest.fixture
def service():
    mock_bot = MagicMock()
    mock_bot.cookies_path = "test_cookies.json"
    mock_bot.browser = MagicMock()
    return SessionService(mock_bot)

class TestSessionServiceLogic:
    def test_is_logged_in_various_urls(self, service):
        # Login page
        service.bot.browser.current_url = "https://www.linkedin.com/login"
        assert service.is_logged_in() is False

        # Challenge page
        service.bot.browser.current_url = "https://www.linkedin.com/checkpoint/challenge"
        assert service.is_logged_in() is False

        # Feed page
        service.bot.browser.current_url = "https://www.linkedin.com/feed/"
        assert service.is_logged_in() is True

        # Jobs page
        service.bot.browser.current_url = "https://www.linkedin.com/jobs/"
        assert service.is_logged_in() is True

        # Profile match
        service.bot.browser.current_url = "https://www.linkedin.com/some-random-page"
        service.bot.browser.find_elements.return_value = [MagicMock()]
        assert service.is_logged_in() is True

        # No profile match
        service.bot.browser.find_elements.return_value = []
        assert service.is_logged_in() is False

    def test_is_logged_in_exception(self, service):
        service.bot.browser.current_url = None
        service.bot.browser.find_elements.side_effect = Exception("Boom")
        assert service.is_logged_in() is False

    def test_restore_session_missing_file(self, service, tmp_path):
        service.bot.cookies_path = str(tmp_path / "missing.json")
        assert service.restore_session_from_cookies() is False
        service.bot.log_event.assert_called_with(
            "cookies_restore_skipped", reason="cookie_file_missing", cookies_path=service.bot.cookies_path
        )

    def test_restore_session_invalid_json(self, service, tmp_path):
        cookie_file = tmp_path / "invalid.json"
        cookie_file.write_text("not json", encoding="utf-8")
        service.bot.cookies_path = str(cookie_file)
        assert service.restore_session_from_cookies() is False

    def test_restore_session_wrong_type(self, service, tmp_path):
        cookie_file = tmp_path / "wrong.json"
        cookie_file.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
        service.bot.cookies_path = str(cookie_file)
        assert service.restore_session_from_cookies() is False
        service.bot.log_event.assert_called_with(
            "cookies_restore_skipped", reason="cookie_file_invalid", cookies_path=service.bot.cookies_path
        )

    def test_restore_session_success(self, service, tmp_path):
        cookie_file = tmp_path / "valid.json"
        cookies = [{"name": "li_at", "value": "abc", "domain": ".www.linkedin.com"}]
        cookie_file.write_text(json.dumps(cookies), encoding="utf-8")
        service.bot.cookies_path = str(cookie_file)

        service.bot.browser.current_url = "https://www.linkedin.com/feed/"
        # Mock is_logged_in to return True
        with patch.object(SessionService, "is_logged_in", return_value=True):
            assert service.restore_session_from_cookies() is True

        service.bot.browser.add_cookie.assert_called()

    def test_save_session_cookies_success(self, service, tmp_path):
        service.bot.cookies_path = str(tmp_path / "saved.json")
        service.bot.browser.get_cookies.return_value = [{"name": "test", "value": "123"}]

        service.save_session_cookies()

        cookie_file = Path(service.bot.cookies_path)
        assert cookie_file.exists()
        with open(cookie_file) as f:
            saved = json.load(f)
        assert saved[0]["name"] == "test"
        service.bot.log_event.assert_called_with(
            "cookies_saved", cookies_path=service.bot.cookies_path, cookie_count=1
        )

    def test_save_session_cookies_failure(self, service, tmp_path):
        service.bot.cookies_path = "/invalid/path/cookies.json"
        service.bot.browser.get_cookies.return_value = []

        service.save_session_cookies()
        service.bot.log_event.assert_called_with(
            "cookies_save_error", cookies_path=service.bot.cookies_path, error=ANY
        )
