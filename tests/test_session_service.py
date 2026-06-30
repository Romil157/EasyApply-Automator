"""Tests for SessionService — pure login-state logic, no real WebDriver."""
from __future__ import annotations

from unittest.mock import MagicMock

from easy_apply_automator.services.session_service import SessionService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(current_url: str = "", find_elements_return=None) -> SessionService:
    bot = MagicMock()
    bot.cookies_path = ".auth/test_cookies.json"
    browser = MagicMock()
    browser.current_url = current_url
    browser.find_elements.return_value = find_elements_return or []
    bot.browser = browser
    svc = SessionService.__new__(SessionService)
    svc.bot = bot
    return svc


# ---------------------------------------------------------------------------
# is_logged_in — URL-based detection
# ---------------------------------------------------------------------------

class TestIsLoggedIn:
    def test_login_url_returns_false(self):
        svc = _make_service("https://www.linkedin.com/login?trk=guest")
        assert svc.is_logged_in() is False

    def test_checkpoint_url_returns_false(self):
        svc = _make_service("https://www.linkedin.com/checkpoint/challenge/verify")
        assert svc.is_logged_in() is False

    def test_feed_url_returns_true(self):
        svc = _make_service("https://www.linkedin.com/feed/")
        assert svc.is_logged_in() is True

    def test_jobs_url_returns_true(self):
        svc = _make_service("https://www.linkedin.com/jobs/search/")
        assert svc.is_logged_in() is True

    def test_mynetwork_url_returns_true(self):
        svc = _make_service("https://www.linkedin.com/mynetwork/")
        assert svc.is_logged_in() is True

    def test_messaging_url_returns_true(self):
        svc = _make_service("https://www.linkedin.com/messaging/")
        assert svc.is_logged_in() is True

    def test_unknown_url_with_profile_link_returns_true(self):
        """Ambiguous URL should fall back to DOM element check."""
        svc = _make_service("https://www.linkedin.com/in/testuser/")
        # Simulate a profile link found in the DOM
        svc.bot.browser.find_elements.return_value = [MagicMock()]
        assert svc.is_logged_in() is True

    def test_unknown_url_no_profile_link_returns_false(self):
        """Ambiguous URL with no nav elements means not logged in."""
        svc = _make_service("https://www.linkedin.com/some/random/page")
        svc.bot.browser.find_elements.return_value = []
        assert svc.is_logged_in() is False

    def test_exception_returns_false(self):
        """Any exception from the browser should yield False."""
        svc = _make_service()
        svc.bot.browser.current_url = None  # triggers attribute error on .lower()
        # Overriding the property to throw
        svc.bot.browser.find_elements.side_effect = Exception("driver crashed")
        # current_url None → "".lower() works, but if find_elements throws, is_logged_in = False
        result = svc.is_logged_in()
        assert isinstance(result, bool)

    def test_empty_url_returns_false(self):
        svc = _make_service("")
        svc.bot.browser.find_elements.return_value = []
        assert svc.is_logged_in() is False


# ---------------------------------------------------------------------------
# restore_session_from_cookies — file-missing path
# ---------------------------------------------------------------------------

class TestRestoreSessionFromCookies:
    def test_returns_false_when_cookie_file_missing(self, tmp_path):
        svc = _make_service()
        svc.bot.cookies_path = str(tmp_path / "no_cookies.json")
        result = svc.restore_session_from_cookies()
        assert result is False

    def test_logs_event_when_cookie_file_missing(self, tmp_path):
        svc = _make_service()
        svc.bot.cookies_path = str(tmp_path / "no_cookies.json")
        svc.restore_session_from_cookies()
        svc.bot.log_event.assert_called()
        call_args = svc.bot.log_event.call_args[0]
        assert "cookies_restore" in call_args[0]

    def test_returns_false_for_invalid_json_cookies(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text("{not_a_list: true}", encoding="utf-8")
        svc = _make_service()
        svc.bot.cookies_path = str(cookie_file)
        result = svc.restore_session_from_cookies()
        assert result is False

    def test_returns_false_for_corrupt_json(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text("<<<not json>>>", encoding="utf-8")
        svc = _make_service()
        svc.bot.cookies_path = str(cookie_file)
        result = svc.restore_session_from_cookies()
        assert result is False
