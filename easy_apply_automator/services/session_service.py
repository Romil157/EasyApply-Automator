"""Service that manages login states, session cookie persistence, and authentication flows."""

from __future__ import annotations

import json
import os
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
from selenium.webdriver.support.ui import WebDriverWait

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
        time.sleep(PAGE_LOAD_PAUSE_SECONDS)

        try:
            if self.is_logged_in():
                log.info("Already logged in to LinkedIn.")
                self.bot.log_event("login_success", method="existing_session")
                return

            email_filled = False
            if username:
                log.info(f"Filling LinkedIn email ID: {username}")
                email_selector = (
                    "input#username, input#session_key, input[name='session_key'], "
                    "input[type='email'], input[autocomplete='username']"
                )
                user_field = None
                elements = self.bot.browser.find_elements(By.CSS_SELECTOR, email_selector)
                for el in elements:
                    if el.is_displayed() and el.is_enabled():
                        user_field = el
                        break

                if not user_field:
                    try:
                        user_field = WebDriverWait(self.bot.browser, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, email_selector))
                        )
                    except Exception:
                        user_field = None

                if user_field:
                    user_field.clear()
                    user_field.send_keys(username)
                    user_field.send_keys(Keys.TAB)
                    email_filled = True
                    time.sleep(MODAL_TRANSITION_PAUSE_SECONDS)
                else:
                    log.warning(
                        "Could not find the email input field on the page. Please enter it manually."
                    )

            pwd_filled = False
            if password:
                log.info("Filling LinkedIn password...")
                pwd_selector = (
                    "input#password, input#session_password, input[name='session_password'], "
                    "input[type='password'], input[autocomplete='current-password']"
                )
                pwd_field = None
                elements = self.bot.browser.find_elements(By.CSS_SELECTOR, pwd_selector)
                for el in elements:
                    if el.is_displayed() and el.is_enabled():
                        pwd_field = el
                        break

                if not pwd_field:
                    try:
                        pwd_field = WebDriverWait(self.bot.browser, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, pwd_selector))
                        )
                    except Exception:
                        pwd_field = None

                if pwd_field:
                    pwd_field.clear()
                    pwd_field.send_keys(password)
                    pwd_filled = True
                    time.sleep(MODAL_TRANSITION_PAUSE_SECONDS)

            if email_filled and pwd_filled:
                submit_selector = (
                    "button[type='submit'], button[data-litms-control-urn*='login-submit'], "
                    "button.btn__primary--large, button[aria-label='Sign in']"
                )
                submit_elements = self.bot.browser.find_elements(By.CSS_SELECTOR, submit_selector)
                for btn in submit_elements:
                    if btn.is_displayed() and btn.is_enabled():
                        try:
                            btn.click()
                            log.info("Submitted login credentials. Waiting for authentication...")
                            break
                        except Exception:
                            pass

            log.info("=" * 50)
            log.info("Please enter your credentials / complete verification in the browser and sign in.")
            log.info("=" * 50)

            # Wait up to 120 seconds for the user to log in manually or verification to finish
            max_wait_seconds = 120
            poll_interval = PAGE_LOAD_PAUSE_SECONDS
            max_checks = int(max_wait_seconds / max(1, poll_interval))

            for i in range(max_checks):
                time.sleep(poll_interval)
                if self.is_logged_in():
                    log.info("Login successful!")
                    self.bot.log_event("login_success", method="manual")
                    return

                if (i + 1) % 5 == 0:
                    remaining = max_wait_seconds - int((i + 1) * poll_interval)
                    if remaining > 0:
                        log.info(f"Waiting for LinkedIn login ({remaining}s remaining)...")

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
            cookie_path = Path(self.bot.cookies_path)
            with open(cookie_path, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            # Tighten file permissions on POSIX hosts so other users on the
            # machine cannot read the LinkedIn session cookies (which are
            # effectively a credential for the session lifetime). On Windows
            # the file is already restricted to the current user via the
            # user-profile directory ACL.
            if os.name == "posix":
                try:
                    os.chmod(cookie_path, 0o600)
                except OSError as exc:
                    log.warning(f"Could not tighten permissions on {cookie_path}: {exc}")
            self.bot.log_event(
                "cookies_saved",
                cookies_path=self.bot.cookies_path,
                cookie_count=len(cookies),
            )
        except Exception as exc:
            self.bot.log_event(
                "cookies_save_error", cookies_path=self.bot.cookies_path, error=str(exc)
            )
