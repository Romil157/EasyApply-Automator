"""WebDriver and Chrome binary detection factory helper routines."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import undetected_chromedriver as uc
from selenium.common.exceptions import WebDriverException

from easy_apply_automator.observability.logger import log


# Patch uc.Chrome.__del__ to prevent OSError: [WinError 6] during interpreter shutdown
def _safe_uc_del(self: uc.Chrome) -> None:
    try:
        self.quit()
    except Exception:
        pass


uc.Chrome.__del__ = _safe_uc_del


def detect_chrome_major_version() -> int | None:
    """Detect main version of installed Google Chrome on Windows registry."""
    if sys.platform == "win32":
        try:
            import winreg

            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    key = winreg.OpenKey(root, r"Software\Google\Chrome\BLBeacon")
                    ver, _ = winreg.QueryValueEx(key, "version")
                    if ver:
                        return int(ver.split(".")[0])
                except Exception:
                    pass
        except Exception:
            pass
    return None


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


def build_browser_options(
    ignore_cert_errors: bool | None = None,
    headless: bool = False,
    user_data_dir: str = "",
    proxy: str = "",
) -> uc.ChromeOptions:
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

    if headless or os.getenv("EASYAPPLY_HEADLESS", "").lower() in ("true", "1", "yes"):
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        log.info("Running browser in headless mode (--headless=new)")

    effective_user_data_dir = user_data_dir or os.getenv("EASYAPPLY_CHROME_USER_DATA_DIR", "")
    if effective_user_data_dir:
        options.add_argument(f"--user-data-dir={effective_user_data_dir}")
        log.info(f"Using persistent Chrome user data directory: {effective_user_data_dir}")

    effective_proxy = proxy or os.getenv("EASYAPPLY_PROXY", "")
    if effective_proxy:
        options.add_argument(f"--proxy-server={effective_proxy}")
        log.info(f"Using proxy server: {effective_proxy}")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=en-US,en")
    return options


def build_webdriver(options: uc.ChromeOptions, chromedriver_path: str | None) -> uc.Chrome:
    log.info("Starting undetected-chromedriver for better anti-detection...")
    version_main = detect_chrome_major_version()
    if version_main:
        log.info(f"Detected Chrome major version: {version_main}")
    try:
        # undetected-chromedriver automatically finds the browser binary
        # but we can pass driver_executable_path if provided
        driver = uc.Chrome(
            options=options,
            driver_executable_path=chromedriver_path,
            version_main=version_main,
            use_subprocess=True,
        )
        return driver
    except Exception as exc:
        log.error(f"Failed to start undetected-chromedriver: {exc}")
        raise WebDriverException(f"Critical failure starting browser: {exc}")
