"""Service that manages login states, session cookie persistence, and authentication flows."""
from __future__ import annotations

import json
import time
from pathlib import Path

from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC

from easy_apply_automator.config.timing import (
    MODAL_TRANSITION_PAUSE_SECONDS,
    PAGE_LOAD_PAUSE_SECONDS,
)
from easy_apply_automator.observability.logger import log

from .base import ServiceBase


class SessionService(ServiceBase):
    """Verifies authentication, signs in to LinkedIn, and restores cookies from cache."""
    def start_linkedin(self, username: str, password: str) -> None:
        log.info("Opening LinkedIn login page...")
        self.bot.browser.get(
            "https://www.linkedin.com/login?trk=guest_homepage-basic_nav-header-signin"
        )
        try:
            if username:
                log.info(f"Filling LinkedIn email ID: {username}")
                user_field = None
                selectors = [
                    (By.ID, "username"),
                    (By.ID, "session_key"),
                    (By.NAME, "session_key"),
                    (By.CSS_SELECTOR, "input[type='email']"),
                    (By.CSS_SELECTOR, "input[autocomplete='username']"),
                ]

                # Check each selector waiting up to 3 seconds for it to be clickable
                for selector in selectors:
                    try:
                        el = self.bot.wait.until(EC.element_to_be_clickable(selector))
                        if el:
                            user_field = el
                            break
                    except Exception:
                        continue

                if user_field:
                    user_field.clear()
                    user_field.send_keys(username)
                    user_field.send_keys(Keys.TAB)
                    time.sleep(MODAL_TRANSITION_PAUSE_SECONDS)
                else:
                    log.warning(
                        "Could not find the email input field on the page. Please enter it manually."
                    )

            log.info("=" * 50)
            log.info("Please enter your email and password in the browser and click 'Sign in'")
            log.info("=" * 50)

            # Wait up to 120 seconds for the user to log in manually
            for _ in range(60):
                time.sleep(PAGE_LOAD_PAUSE_SECONDS)
                if self.is_logged_in():
                    log.info("Login successful!")
                    self.bot.log_event("login_success", method="manual")
                    return

            log.warning("Login timed out. Please restart the bot and try again.")
            self.bot.log_event(
                "login_timeout",
                method="manual",
                current_url=self.bot.browser.current_url,
            )
        except (TimeoutException, NoSuchElementException, WebDriverException) as exc:
            log.error(f"Login flow failed: {exc}")
            self.bot.log_event("login_error", method="manual", error=str(exc))

    def is_logged_in(self) -> bool:
        try:
            current_url = (self.bot.browser.current_url or "").lower()
            if "/login" in current_url or "/checkpoint/challenge" in current_url:
                return False
            if any(path in current_url for path in ("/feed", "/jobs", "/mynetwork", "/messaging")):
                return True
            return (
                len(
                    self.bot.browser.find_elements(
                        By.CSS_SELECTOR,
                        "a[data-test-global-nav-link='profile'], a[href*='/in/']",
                    )
                )
                > 0
            )
        except Exception:
            return False

    def restore_session_from_cookies(self) -> bool:
        cookie_file = Path(self.bot.cookies_path)
        if not cookie_file.exists():
            self.bot.log_event(
                "cookies_restore_skipped",
                reason="cookie_file_missing",
                cookies_path=self.bot.cookies_path,
            )
            return False

        try:
            with open(cookie_file, encoding="utf-8") as f:
                cookies = json.load(f)
            if not isinstance(cookies, list):
                self.bot.log_event(
                    "cookies_restore_skipped",
                    reason="cookie_file_invalid",
                    cookies_path=self.bot.cookies_path,
                )
                return False

            self.bot.browser.get("https://www.linkedin.com/")
            for cookie in cookies:
                if not isinstance(cookie, dict):
                    continue
                c = dict(cookie)
                if "sameSite" in c and c["sameSite"] not in ("Strict", "Lax", "None"):
                    c.pop("sameSite", None)
                if "expiry" in c:
                    try:
                        c["expiry"] = int(c["expiry"])
                    except Exception:
                        c.pop("expiry", None)
                try:
                    self.bot.browser.add_cookie(c)
                except Exception:
                    continue

            self.bot.browser.get("https://www.linkedin.com/feed/")
            time.sleep(PAGE_LOAD_PAUSE_SECONDS)
            ok = self.is_logged_in()
            self.bot.log_event(
                "cookies_restore_result",
                success=ok,
                cookies_path=self.bot.cookies_path,
                current_url=self.bot.browser.current_url,
            )
            return ok
        except Exception as exc:
            self.bot.log_event(
                "cookies_restore_error",
                cookies_path=self.bot.cookies_path,
                error=str(exc),
            )
            return False

    def save_session_cookies(self) -> None:
        try:
            cookies = self.bot.browser.get_cookies()
            with open(self.bot.cookies_path, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            self.bot.log_event(
                "cookies_saved",
                cookies_path=self.bot.cookies_path,
                cookie_count=len(cookies),
            )
        except Exception as exc:
            self.bot.log_event(
                "cookies_save_error", cookies_path=self.bot.cookies_path, error=str(exc)
            )
