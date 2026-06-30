from __future__ import annotations

import os
import random
import re
import shutil
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import pyautogui
from bs4 import BeautifulSoup
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from easy_apply_automator.app.search_loop import SearchLoopMixin
from easy_apply_automator.domain.models import AppConfig
from easy_apply_automator.infra.browser_factory import (
    build_browser_options,
    build_webdriver,
    detect_chrome_binary,
)
from easy_apply_automator.infra.repositories import (
    ResultsRepository,
    load_recent_applied_ids,
)
from easy_apply_automator.observability.events import EventLogger
from easy_apply_automator.observability.logger import log, setup_logger
from easy_apply_automator.qa.auto_answer import AutoAnswer
from easy_apply_automator.services.apply_flow_service import ApplyFlowService
from easy_apply_automator.services.diagnostics_service import DiagnosticsService
from easy_apply_automator.services.question_service import QuestionService
from easy_apply_automator.services.session_service import SessionService
from easy_apply_automator.services.throughput_service import ThroughputService


class LinkedInEasyApplyOrchestrator(SearchLoopMixin):
    MIN_SESSION_SECONDS = 3 * 60 * 60
    MAX_SESSION_SECONDS = 5 * 60 * 60

    def __init__(self, config: AppConfig) -> None:
        setup_logger()
        log.info("Welcome to Easy Apply Bot")
        log.info(f"current directory is : {os.getcwd()}")
        log.info("Please wait while we prepare the bot for you")

        if config.experience_level:
            experience_levels = {
                1: "Internship",
                2: "Entry level",
                3: "Associate",
                4: "Mid-Senior level",
                5: "Director",
                6: "Executive",
            }
            applied_levels = [
                experience_levels[level]
                for level in config.experience_level
                if level in experience_levels
            ]
            log.info(
                "Applying for experience level roles: " + ", ".join(applied_levels)
            )
        else:
            log.info("Applying for all experience levels")

        self.uploads = config.uploads
        self.salary = config.salary
        self.rate = config.rate
        self.phone_number = config.phone_number
        self.location_country = config.location_country
        self.location_city = config.location_city
        self.blacklist = config.blacklist
        self.blacklist_titles = config.blacklist_titles
        self.experience_level = config.experience_level
        self.max_pages_per_search = max(1, int(config.runtime.max_pages_per_search))

        self.results_filename = config.results_filename
        self.events_filename = config.events_filename
        self.cookies_path = config.cookies_path
        Path(self.results_filename).parent.mkdir(parents=True, exist_ok=True)
        Path(self.events_filename).parent.mkdir(parents=True, exist_ok=True)
        Path(self.cookies_path).parent.mkdir(parents=True, exist_ok=True)

        past_ids = load_recent_applied_ids(self.results_filename)
        self.appliedJobIDs: list[str] = past_ids if past_ids is not None else []
        self.results_repo = ResultsRepository(self.results_filename)
        self.event_logger = EventLogger(self.events_filename)

        self.options = build_browser_options()
        chromedriver_path = shutil.which("chromedriver")
        chrome_path = detect_chrome_binary()
        if chrome_path:
            self.options.binary_location = chrome_path
            log.info(f"Using browser binary: {chrome_path}")
        else:
            log.warning(
                "No explicit Chromium/Chrome binary found in PATH. "
                "Proceeding with Selenium default browser discovery."
            )

        self.browser = build_webdriver(self.options, chromedriver_path)
        self.wait = WebDriverWait(self.browser, 30)

        self.database_related_title_keywords = [
            "database",
            "db ",
            " db",
            "sql",
            "postgres",
            "postgresql",
            "mysql",
            "mariadb",
            "oracle",
            "mongodb",
            "redis",
            "snowflake",
            "bigquery",
            "databricks",
            "data warehouse",
            "etl",
            "data engineer",
            "data engineering",
            "dba",
            "data platform",
            "data architect",
        ]
        self.medical_related_keywords = [
            "medical",
            "healthcare",
            "health care",
            "clinical",
            "hospital",
            "patient",
            "pharma",
            "pharmaceutical",
            "biotech",
            "biosciences",
            "therapeutic",
            "therapeutics",
            "oncology",
            "nurse",
            "nursing",
            "physician",
            "dmpk",
            "pharmacology",
            "medtech",
            "ehr",
            "emr",
            "life sciences",
            "life science",
            "mental health",
            "diagnostic",
            "diagnostics",
        ]

        self.locator = {
            "next": (By.CSS_SELECTOR, "button[aria-label='Continue to next step']"),
            "review": (By.CSS_SELECTOR, "button[aria-label='Review your application']"),
            "submit": (By.CSS_SELECTOR, "button[aria-label='Submit application']"),
            "error": (By.CLASS_NAME, "artdeco-inline-feedback__message"),
            "upload_resume": (
                By.XPATH,
                "//*[contains(@id, 'jobs-document-upload-file-input-upload-resume')]",
            ),
            "upload_cv": (
                By.XPATH,
                "//*[contains(@id, 'jobs-document-upload-file-input-upload-cover-letter')]",
            ),
            "follow": (By.CSS_SELECTOR, "label[for='follow-company-checkbox']"),
            "upload": (By.NAME, "file"),
            "search": (By.CLASS_NAME, "jobs-search-results-list"),
            "links": ("xpath", "//div[@data-job-id]"),
            "fields": (By.CLASS_NAME, "jobs-easy-apply-form-section__grouping"),
            "radio_select": (By.CSS_SELECTOR, "input[type='radio']"),
            "multi_select": (
                By.XPATH,
                "//*[contains(@id, 'text-entity-list-form-component') ]",
            ),
            "text_select": (By.CLASS_NAME, "artdeco-text-input--input"),
            "2fa_oneClick": (By.ID, "reset-password-submit-button"),
            "easy_apply_button": (
                By.XPATH,
                "//button[contains(@class, 'jobs-apply-button') ]",
            ),
        }

        self.positions: list[str] = []
        self.locations: list[str] = []
        self.job_page = None

        self.session_duration_seconds = random.randint(
            int(max(30 * 60, float(config.runtime.session_duration_hours_min) * 3600)),
            int(
                max(
                    max(
                        30 * 60, float(config.runtime.session_duration_hours_min) * 3600
                    ),
                    float(config.runtime.session_duration_hours_max) * 3600,
                )
            ),
        )
        self.session_deadline = 0.0
        self.max_apply_seconds = int(config.runtime.max_apply_seconds)
        self.short_break_min_seconds = max(
            5, int(config.runtime.short_break_min_seconds)
        )
        self.short_break_max_seconds = max(
            self.short_break_min_seconds, int(config.runtime.short_break_max_seconds)
        )
        self.short_break_every_min_minutes = max(
            1, int(config.runtime.short_break_every_min_minutes)
        )
        self.short_break_every_max_minutes = max(
            self.short_break_every_min_minutes,
            int(config.runtime.short_break_every_max_minutes),
        )
        self.shuffle_search_combos = bool(config.runtime.shuffle_search_combos)
        self.next_short_break_at = 0.0
        self.throughput_window_seconds = max(
            60, int(config.runtime.throughput_window_minutes) * 60
        )

        self.session_started_at = 0.0
        self.session_jobs_processed = 0
        self.session_jobs_submitted = 0
        self.session_jobs_attempted = 0
        self.session_jobs_failed_attempts = 0
        self.session_jobs_failed_medical = 0
        self.submitted_timestamps: deque[float] = deque(maxlen=1000)
        self.stop_requested = False
        self.stop_reason: str | None = None

        self.debug_root = Path("debug")
        self.debug_root.mkdir(parents=True, exist_ok=True)
        self.debug_failed_root = self.debug_root / "failed"
        self.debug_failed_root.mkdir(parents=True, exist_ok=True)
        self.first_job_debug_done = False
        self.current_job_id: str | None = None
        self.current_job_debug_dir: Path | None = None
        self.current_job_first_try_dir: Path | None = None
        self.current_job_debug_step = 0
        self.current_job_failure_count = 0

        # Keep QA answers in memory only; no runtime CSV file creation.
        self.qa_file: Path | None = None
        self.answers: dict[str, str] = {}

        self.auto_answer = AutoAnswer(
            qa_file=self.qa_file,
            ans_yaml_path=Path(config.ans_yaml_path),
            salary=str(self.salary),
            hourly_rate=str(self.rate),
            answers=self.answers,
            log=log,
            linkedin_profile_url=config.linkedin_profile_url,
        )

        self.diagnostics = DiagnosticsService(self)
        self.questions = QuestionService(self)
        self.apply_flow = ApplyFlowService(self)
        self.throughput = ThroughputService(self)
        self.session = SessionService(self)

        restored = self.restore_session_from_cookies()
        if not restored:
            self.start_linkedin(config.username, config.password)
            self.save_session_cookies()

        self.log_event(
            "bot_initialized",
            results_json=self.results_filename,
            events_jsonl=self.events_filename,
            cookies_path=self.cookies_path,
            experience_levels=self.experience_level,
        )

    def log_event(self, event: str, **fields) -> None:
        self.event_logger.log_event(event, **fields)

    def request_stop(self, reason: str, **fields) -> None:
        self.stop_requested = True
        self.stop_reason = reason
        self.session_deadline = 0.0
        self.log_event("stop_requested", reason=reason, **fields)

    def _start_job_debug_trace(self, job_id: str) -> None:
        self.diagnostics.start_job_debug_trace(job_id)

    def _finish_job_debug_trace(self) -> None:
        self.diagnostics.finish_job_debug_trace()

    def _dump_debug_html(
        self, tag: str, force_dir: Path | None = None, extra: dict | None = None
    ) -> None:
        self.diagnostics.dump_debug_html(tag, force_dir=force_dir, extra=extra)

    def _dump_failure_snapshot(
        self, reason: str, force_failed_root: bool = False
    ) -> None:
        self.diagnostics.dump_failure_snapshot(
            reason, force_failed_root=force_failed_root
        )

    def _extract_job_metadata(self, job_id: str | None = None) -> dict:
        return self.diagnostics.extract_job_metadata(job_id=job_id)

    def _medical_keyword_match(self) -> str | None:
        return self.diagnostics.medical_keyword_match()

    def _coerce_numeric_answer(self, question: str, answer: str) -> str:
        return self.questions.coerce_numeric_answer(question, answer)

    def _normalize_text_answer(
        self, question: str, answer: str, input_id: str = ""
    ) -> str:
        return self.questions.normalize_text_answer(question, answer, input_id)

    def _clean_question_text(self, question: str) -> str:
        return self.questions.clean_question_text(question)

    def _answer_aliases(self, answer: str) -> set[str]:
        return self.questions.answer_aliases(answer)

    def _radio_matches_answer(self, field, radio, answer: str) -> bool:
        return self.questions.radio_matches_answer(field, radio, answer)

    def _derive_direct_answer(self, question: str, input_id: str = "") -> str | None:
        return self.questions.derive_direct_answer(question, input_id)

    def process_questions(self) -> None:
        self.questions.process_questions()

    def ans_question(self, question: str) -> str:
        return self.questions.ans_question(question)

    def _get_easy_apply_progress(self) -> int | None:
        return self.apply_flow.get_easy_apply_progress()

    def _is_already_applied_job_page(self) -> bool:
        return self.apply_flow.is_already_applied_job_page()

    def send_resume(self) -> bool:
        return self.apply_flow.send_resume()

    def _schedule_next_short_break(self) -> None:
        self.throughput.schedule_next_short_break()

    def _maybe_take_short_break(self, source: str) -> None:
        self.throughput.maybe_take_short_break(source)

    def _update_session_throughput(
        self, *, reason: str, attempted: bool, result: bool
    ) -> None:
        self.throughput.update_session_throughput(
            reason=reason, attempted=attempted, result=result
        )

    def start_linkedin(self, username: str, password: str) -> None:
        self.session.start_linkedin(username, password)

    def _is_logged_in(self) -> bool:
        return self.session.is_logged_in()

    def restore_session_from_cookies(self) -> bool:
        return self.session.restore_session_from_cookies()

    def save_session_cookies(self) -> None:
        self.session.save_session_cookies()

    @staticmethod
    def get_applied_ids(filename: str) -> list[str] | None:
        return load_recent_applied_ids(filename)

    def fill_data(self) -> None:
        self.browser.set_window_size(1, 1)
        self.browser.set_window_position(2000, 2000)

    def start_apply(self, positions: list[str], locations: list[str]) -> None:
        self.fill_data()
        self.positions = positions
        self.locations = locations
        randomized_positions = list(positions)
        random.shuffle(randomized_positions)
        self.session_started_at = time.time()
        self.session_jobs_processed = 0
        self.session_jobs_submitted = 0
        self.session_jobs_attempted = 0
        self.session_jobs_failed_attempts = 0
        self.session_jobs_failed_medical = 0
        self.submitted_timestamps.clear()
        self.stop_requested = False
        self.stop_reason = None
        self.session_deadline = time.time() + self.session_duration_seconds
        self._schedule_next_short_break()
        self.log_event(
            "session_start",
            duration_seconds=self.session_duration_seconds,
            duration_minutes=round(self.session_duration_seconds / 60, 2),
            positions_count=len(positions),
            locations_count=len(locations),
            randomized_positions=randomized_positions,
        )
        combos = [
            (position, location)
            for position in randomized_positions
            for location in locations
        ]
        if self.shuffle_search_combos:
            random.shuffle(combos)

        for position, location in combos[:500]:
            if self.stop_requested or time.time() >= self.session_deadline:
                self.log_event(
                    "session_deadline_reached",
                    stop_reason=self.stop_reason or "time_budget_exhausted",
                )
                break
            self._maybe_take_short_break(source="combo_loop")
            log.info(f"Applying to {position}: {location}")
            self.log_event("combo_start", position=position, location=location)
            self.applications_loop(position, f"&location={location}")



    def apply_to_job(self, job_id: str) -> bool:
        self._start_job_debug_trace(str(job_id))
        self._dump_debug_html("job_open_start")

        self.get_job_page(job_id)
        self._dump_debug_html("job_page_loaded")
        time.sleep(0.1)

        if not self._matches_selected_experience_level():
            log.info(f"Skipping job {job_id} because it does not match the selected experience level filter.")
            self.log_event(
                "job_skipped_experience_level_mismatch",
                job_id=str(job_id),
                title=self.browser.title,
                selected_experience_level=self.experience_level,
            )
            self._finish_job_debug_trace()
            return False

        button = self.get_easy_apply_button()
        self._dump_debug_html(
            "easy_apply_button_detected", extra={"button_found": bool(button)}
        )

        if self._is_daily_limit_reached():
            log.warning(
                "LinkedIn daily application limit reached. Stopping the bot session."
            )
            self.request_stop(
                "daily_easy_apply_limit_reached",
                job_id=str(job_id),
            )
            self.log_event("daily_limit_reached", job_id=str(job_id))
            self._finish_job_debug_trace()
            return False

        if button is not False:
            normalized_title = f" {self.browser.title.lower()} "
            matched_medical_keyword = self._medical_keyword_match()
            matched_blacklist_title = next(
                (
                    word
                    for word in self.blacklist_titles
                    if word.lower() in normalized_title
                ),
                None,
            )
            matched_database_title = next(
                (
                    word
                    for word in self.database_related_title_keywords
                    if word.lower() in normalized_title
                ),
                None,
            )

            if matched_medical_keyword:
                log.info(
                    f"Skipping this application, medical-related keyword found: '{matched_medical_keyword}'."
                )
                self.log_event(
                    "job_skipped_medical_related",
                    job_id=str(job_id),
                    title=self.browser.title,
                    matched_keyword=matched_medical_keyword,
                )
                string_easy = "* Medical-related role skipped"
                result = False
                reason = "medical_related_title"
            elif matched_blacklist_title:
                log.info(
                    "skipping this application, a blacklisted keyword was found in the job position"
                )
                string_easy = "* Contains blacklisted keyword"
                result = False
                reason = "title_blacklisted"
            elif matched_database_title:
                log.info(
                    "Skipping this application, database-related keyword found in title."
                )
                self.log_event(
                    "job_skipped_database_related_title",
                    job_id=str(job_id),
                    title=self.browser.title,
                    matched_keyword=matched_database_title,
                )
                string_easy = "* Contains database-related keyword"
                result = False
                reason = "database_related_title"
            else:
                string_easy = "* has Easy Apply Button"
                log.info("Clicking the EASY apply button")
                self._click_easy_apply(button)
                self._dump_debug_html("easy_apply_clicked")
                time.sleep(1)
                self.fill_out_fields()
                result = self.send_resume()
                if result:
                    string_easy = "*Applied: Sent Resume"
                    reason = "submitted"
                elif (
                    self.stop_requested
                    and self.stop_reason == "daily_easy_apply_limit_reached"
                ):
                    string_easy = "*Stopped: LinkedIn Easy Apply daily limit reached"
                    reason = "daily_limit_reached"
                else:
                    string_easy = "*Did not apply: Failed to send Resume"
                    reason = "apply_flow_failed"
        elif self._is_already_applied_job_page():
            log.info(
                "You have already applied to this position. (verified by top-card apply status)"
            )
            string_easy = "* Already Applied"
            result = False
            reason = "already_applied"
        else:
            log.info("The Easy apply button does not exist.")
            string_easy = "* Doesn't have Easy Apply Button"
            result = False
            reason = "no_easy_apply_button"

        log.info(f"\nPosition {job_id}:\n {self.browser.title} \n {string_easy} \n")

        metadata = self._extract_job_metadata(job_id=job_id)
        self.log_event(
            "job_processed",
            attempted=bool(button),
            result=bool(result),
            reason=reason,
            easy_apply_button=bool(button),
            **metadata,
        )
        self.write_to_file(button, job_id, self.browser.title, result, metadata, reason)
        self._update_session_throughput(
            reason=reason, attempted=bool(button), result=bool(result)
        )
        if not result and reason != "daily_limit_reached":
            self._dump_failure_snapshot(
                f"job_result_{reason}",
                force_failed_root=(reason == "medical_related_title"),
            )
        self._finish_job_debug_trace()
        return result

    def write_to_file(
        self,
        button,
        job_id,
        browser_title,
        result,
        metadata: dict | None = None,
        reason: str | None = None,
    ) -> None:
        def re_extract(text, pattern):
            target = re.search(pattern, text)
            return target.group(1) if target else target

        timestamp = datetime.now().isoformat(timespec="seconds")
        attempted = button is not False
        title_parts = (
            browser_title.split(" | ")
            if browser_title
            else ["Unknown Role", "Unknown Company"]
        )
        job_text = title_parts[0] if len(title_parts) > 0 else "Unknown Role"
        company_text = title_parts[1] if len(title_parts) > 1 else "Unknown Company"
        job = re_extract(job_text, r"\(?\d?\)?\s?(\w.*)") or job_text
        company = re_extract(company_text, r"(\w.*)") or company_text

        record = {
            "timestamp": timestamp,
            "job_id": str(job_id),
            "job_title": job,
            "company": company,
            "attempted": attempted,
            "result": bool(result),
            "reason": reason,
            "metadata": metadata or {},
        }
        try:
            self.results_repo.append(record)
            job_id_str = str(job_id)
            if job_id_str not in self.appliedJobIDs:
                self.appliedJobIDs.append(job_id_str)
            self.log_event(
                "results_write_ok", results_json=self.results_filename, record=record
            )
        except Exception as exc:
            self.log_event(
                "results_write_error",
                results_json=self.results_filename,
                error=str(exc),
                record=record,
            )
            raise

    def get_job_page(self, job_id):
        job = f"https://www.linkedin.com/jobs/view/{job_id}"
        self.browser.get(job)
        self.job_page = self.load_page(sleep=0.02, scroll_limit=500)
        return self.job_page

    def _is_daily_limit_reached(self) -> bool:
        try:
            detected, _ = self.apply_flow.detect_daily_easy_apply_limit()
            return detected
        except Exception:
            return False

    def get_easy_apply_button(self):
        try:
            self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "button, a, a[role='button']")
                )
            )
        except Exception:
            pass

        selectors = [
            (By.ID, "jobs-apply-button-id"),
            (By.CSS_SELECTOR, "button.jobs-apply-button"),
            (By.CSS_SELECTOR, "button[data-live-test-job-apply-button]"),
            (By.CSS_SELECTOR, "button[aria-label*='Easy Apply']"),
            (By.CSS_SELECTOR, "a[aria-label*='Easy Apply']"),
            (By.CSS_SELECTOR, "a[data-view-name='job-apply-button']"),
            (By.CSS_SELECTOR, "a[href*='/jobs/view/'][href*='/apply/']"),
            (By.XPATH, "//button[contains(@aria-label, 'Easy Apply')]"),
            (By.XPATH, "//button[.//span[contains(normalize-space(), 'Easy Apply')]]"),
            (By.XPATH, "//a[contains(@aria-label, 'Easy Apply')]"),
            (
                By.XPATH,
                "//a[.//*[contains(normalize-space(), 'Easy Apply')] or contains(normalize-space(), 'Easy Apply')]",
            ),
        ]

        candidates = []
        for by, value in selectors:
            try:
                candidates.extend(self.browser.find_elements(by, value))
            except Exception:
                continue

        seen_ids = set()
        deduped = []
        for elem in candidates:
            elem_id = elem.id
            if elem_id not in seen_ids:
                seen_ids.add(elem_id)
                deduped.append(elem)

        for button in deduped:
            try:
                aria = (button.get_attribute("aria-label") or "").lower()
                text = (button.text or "").strip().lower()
                is_easy_apply = "easy apply" in aria or "easy apply" in text
                if not is_easy_apply:
                    continue
                if button.is_displayed() and button.is_enabled():
                    return button
            except Exception:
                continue

        try:
            for button in self.browser.find_elements(By.CSS_SELECTOR, "button, a"):
                aria = (button.get_attribute("aria-label") or "").lower()
                text = (button.text or "").strip().lower()
                if "easy apply" in aria or "easy apply" in text:
                    if button.is_displayed() and button.is_enabled():
                        return button
        except Exception:
            pass

        log.debug("Easy Apply button not found after all selector strategies")
        return False

    def _click_easy_apply(self, element) -> None:
        self.browser.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", element
        )
        time.sleep(0.2)
        try:
            element.click()
            return
        except Exception:
            pass
        try:
            self.browser.execute_script("arguments[0].click();", element)
            return
        except Exception as exc:
            raise WebDriverException(f"Failed to click Easy Apply control: {exc}")

    def fill_out_fields(self):
        fields = self.browser.find_elements(
            By.CLASS_NAME, "jobs-easy-apply-form-section__grouping"
        )
        for field in fields:
            if "Mobile phone number" in field.text:
                field_input = field.find_element(By.TAG_NAME, "input")
                field_input.clear()
                field_input.send_keys(self.phone_number)

    def get_elements(self, element_type) -> list:
        elements = []
        element = self.locator[element_type]
        if self.is_present(element):
            elements = self.browser.find_elements(element[0], element[1])
        return elements

    def is_present(self, locator) -> bool:
        return len(self.browser.find_elements(locator[0], locator[1])) > 0

    def _safe_click(self, element) -> bool:
        try:
            self.browser.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", element
            )
            time.sleep(0.2)
            element.click()
            return True
        except Exception:
            pass
        try:
            self.browser.execute_script("arguments[0].click();", element)
            return True
        except Exception:
            return False

    def _find_clickable(self, selectors: list[tuple[str, str]]):
        for by, value in selectors:
            try:
                elements = self.browser.find_elements(by, value)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        return element
            except Exception:
                continue
        return None

    def _select_non_default_option(self, select_element) -> bool:
        try:
            options = select_element.find_elements(By.TAG_NAME, "option")
            for option in options:
                text = (option.text or "").strip().lower()
                value = (option.get_attribute("value") or "").strip().lower()
                if (
                    not text
                    or "select an option" in text
                    or value in ("", "select an option")
                ):
                    continue
                option.click()
                return True
        except Exception:
            return False
        return False

    def _select_option_by_answer(self, select_element, answer: str) -> bool:
        answer_norm = (answer or "").strip().lower()
        if not answer_norm:
            return False
        try:
            options = select_element.find_elements(By.TAG_NAME, "option")
            for option in options:
                text = (option.text or "").strip()
                value = (option.get_attribute("value") or "").strip()
                if text.lower() == answer_norm or value.lower() == answer_norm:
                    option.click()
                    return True
            for option in options:
                text = (option.text or "").strip().lower()
                value = (option.get_attribute("value") or "").strip().lower()
                if answer_norm in text or answer_norm in value:
                    option.click()
                    return True
        except Exception:
            return False
        return False

    def _fill_typeahead_input(self, input_el, answer: str) -> bool:
        """Type into a combobox/typeahead field and click the first dropdown suggestion."""
        try:
            input_el.clear()
            input_el.send_keys(answer)
            time.sleep(0.4)
            for selector in [
                "div[role='option'].basic-typeahead__selectable",
                "[role='listbox'] [role='option']",
                "li[role='option']",
            ]:
                opts = self.browser.find_elements(By.CSS_SELECTOR, selector)
                visible = [o for o in opts if o.is_displayed()]
                if visible:
                    self.browser.execute_script("arguments[0].click();", visible[0])
                    return True
        except Exception:
            pass
        return False

    def load_page(self, sleep: float = 0.1, scroll_limit: int = 1500, scroll_step: int = 500):
        scroll_page = 0
        while scroll_page < scroll_limit:
            self.browser.execute_script(f"window.scrollTo(0,{scroll_page} );")
            scroll_page += scroll_step
            time.sleep(sleep)

        if scroll_limit > 0:
            self.browser.execute_script("window.scrollTo(0,0);")
            time.sleep(sleep)

        return BeautifulSoup(self.browser.page_source, "lxml")

    def avoid_lock(self) -> None:
        x, _ = pyautogui.position()
        pyautogui.moveTo(x + 200, pyautogui.position().y, duration=1.0)
        pyautogui.moveTo(x, pyautogui.position().y, duration=0.5)
        pyautogui.keyDown("ctrl")
        pyautogui.press("esc")
        pyautogui.keyUp("ctrl")
        time.sleep(0.5)
        pyautogui.press("esc")


