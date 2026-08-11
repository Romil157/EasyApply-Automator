"""WebDriver and Chrome binary detection factory helper routines."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import undetected_chromedriver as uc
from selenium.common.exceptions import SessionNotCreatedException, WebDriverException
from selenium.webdriver.chrome.service import Service as ChromeService

from easy_apply_automator.observability.logger import log


def detect_chrome_binary() -> str | None:
    for env_var in ("CHROME_BIN", "GOOGLE_CHROME_BIN", "CHROMIUM_PATH", "CHROME_PATH"):
        candidate = os.getenv(env_var)
        if candidate and Path(candidate).exists():
            return candidate

    for name in ("chromium", "google-chrome", "chrome", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path

    macos_candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        str(Path.home() / "Applications/Chromium.app/Contents/MacOS/Chromium"),
    ]
    for candidate in macos_candidates:
        if Path(candidate).exists():
            return candidate

    return None


def build_browser_options(ignore_cert_errors: bool | None = None) -> uc.ChromeOptions:
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")

    if ignore_cert_errors is None:
        val = os.getenv("EASYAPPLY_IGNORE_CERT_ERRORS", "false").lower()
        ignore_cert_errors = val in ("true", "1", "yes")

    if ignore_cert_errors:
        options.add_argument("--ignore-certificate-errors")
        log.warning(
            "Certificate validation is disabled (--ignore-certificate-errors). "
            "This should only be done for corporate TLS-inspecting proxy compatibility."
        )

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-extensions")
    # AutomationControlled is handled by undetected-chromedriver by default
    return options


def build_webdriver(
    options: uc.ChromeOptions, chromedriver_path: str | None
) -> uc.Chrome:
    log.info("Starting undetected-chromedriver for better anti-detection...")
    try:
        # undetected-chromedriver automatically finds the browser binary
        # but we can pass driver_executable_path if provided
        driver = uc.Chrome(
            options=options,
            driver_executable_path=chromedriver_path,
            use_subprocess=True
        )
        return driver
    except Exception as exc:
        log.error(f"Failed to start undetected-chromedriver: {exc}")
        raise WebDriverException(f"Critical failure starting browser: {exc}")
