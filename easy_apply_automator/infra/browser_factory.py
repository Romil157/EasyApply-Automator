from __future__ import annotations

import os
import shutil
from pathlib import Path

from selenium import webdriver
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


def build_browser_options() -> webdriver.ChromeOptions:
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-blink-features")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return options


def build_webdriver(
    options: webdriver.ChromeOptions, chromedriver_path: str | None
) -> webdriver.Chrome:
    if chromedriver_path:
        try:
            return webdriver.Chrome(service=ChromeService(chromedriver_path), options=options)
        except SessionNotCreatedException as exc:
            log.warning(
                "Chromedriver at PATH is incompatible with your Chrome version. "
                "Retrying with Selenium Manager auto-driver resolution."
            )
            log.debug(f"Original driver error: {exc}")
        except WebDriverException as exc:
            log.warning(
                "Failed to start with chromedriver from PATH. "
                "Retrying with Selenium Manager auto-driver resolution."
            )
            log.debug(f"Original driver error: {exc}")

    log.info("Starting Chrome via Selenium Manager (auto driver resolution).")
    original_path = os.environ.get("PATH", "")
    try:
        filtered_entries = []
        for path_entry in original_path.split(os.pathsep):
            chromedriver_candidate = Path(path_entry) / "chromedriver"
            if chromedriver_candidate.exists():
                continue
            filtered_entries.append(path_entry)
        os.environ["PATH"] = os.pathsep.join(filtered_entries)
        return webdriver.Chrome(options=options)
    finally:
        os.environ["PATH"] = original_path
