"""Primary orchestrator coordinating LinkedIn Easy Apply automation workflow."""

from __future__ import annotations

import random
import re
import shutil
import time
from collections import deque
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from easy_apply_automator.app.search_loop import SearchLoopMixin
from easy_apply_automator.config.timing import (
    CLICK_PAUSE_SECONDS,
    MICRO_PAUSE_SECONDS,
    MODAL_TRANSITION_PAUSE_SECONDS,
    QUESTION_LOAD_PAUSE_SECONDS,
    TYPEAHEAD_PAUSE_SECONDS,
)
from easy_apply_automator.domain.models import AppConfig
from easy_apply_automator.infra.browser_factory import (
    build_browser_options,
    build_webdriver,
    detect_chrome_binary,
)
from easy_apply_automator.infra.human_simulation import (
    AdaptiveCircuitBreaker,
    human_type_with_jitter,
    reading_pause,
    smooth_scroll_to,
)
from easy_apply_automator.infra.repositories import (
    ResultsRepository,
    load_recent_applied_ids,
)
from easy_apply_automator.observability.events import EventLogger
from easy_apply_automator.observability.logger import log
from easy_apply_automator.qa.auto_answer import AutoAnswer
from easy_apply_automator.qa.relevance_scorer import RelevanceScorer
from easy_apply_automator.services.apply_flow_service import ApplyFlowService
from easy_apply_automator.services.diagnostics_service import DiagnosticsService
from easy_apply_automator.services.question_service import QuestionService
from easy_apply_automator.services.session_service import SessionService
from easy_apply_automator.services.throughput_service import ThroughputService


class LinkedInEasyApplyOrchestrator(SearchLoopMixin):
    def __init__(self, config: AppConfig) -> None:
        self._init_config(config)
        self._init_browser(config)
        self._init_services(config)

    def _init_config(self, config: AppConfig) -> None:
        self.runtime = config.runtime
        self.uploads = config.uploads
        self.salary = config.salary
        self.rate = config.rate
        self.phone_number = config.phone_number
        self.location_country = config.location_country
        self.location_city = config.location_city
        self.blacklist = config.blacklist
        self.blacklist_titles = config.blacklist_titles
        self.experience_level = config.experience_level
        self.max_pages_per_search = max(1, config.runtime.max_pages_per_search)
        self.max_applications = config.runtime.max_applications
        self.dry_run = config.runtime.dry_run
        self.date_posted = config.date_posted
        self.workplace_types = config.workplace_types
        self.job_types = config.job_types

        self.results_filename = config.results_filename
        self.events_filename = config.events_filename
        self.cookies_path = config.cookies_path
        for path_str in (self.results_filename, self.events_filename, self.cookies_path):
            Path(path_str).parent.mkdir(parents=True, exist_ok=True)

        past_ids = load_recent_applied_ids(self.results_filename)
        self.appliedJobIDs = past_ids if past_ids is not None else []
        self.session_failed_ids: set[str] = set()
        self.results_repo = ResultsRepository(self.results_filename)
        self.event_logger = EventLogger(self.events_filename)

        self.database_related_title_keywords = config.filters.get("database_related", [])
        self.medical_related_keywords = config.filters.get("medical_related", [])

        by_map = {"css": By.CSS_SELECTOR, "xpath": By.XPATH, "id": By.ID, "class": By.CLASS_NAME, "name": By.NAME}
        self.locator = {
            k: (by_map.get(v[0], By.CSS_SELECTOR), v[1])
            for k, v in config.locators.items()
            if isinstance(v, list) and len(v) == 2
        }

        self.positions: list[str] = []
        self.locations: list[str] = []
        self.job_page = None

        min_dur = int(max(30 * 60, config.runtime.session_duration_hours_min * 3600))
        max_dur = int(max(min_dur, config.runtime.session_duration_hours_max * 3600))
        self.session_duration_seconds = random.randint(min_dur, max_dur)
        self.session_deadline = 0.0
        self.max_apply_seconds = config.runtime.max_apply_seconds
        self.short_break_min_seconds = max(5, config.runtime.short_break_min_seconds)
        self.short_break_max_seconds = max(self.short_break_min_seconds, config.runtime.short_break_max_seconds)
        self.short_break_every_min_minutes = max(1, config.runtime.short_break_every_min_minutes)
        self.short_break_every_max_minutes = max(self.short_break_every_min_minutes, config.runtime.short_break_every_max_minutes)
        self.shuffle_search_combos = config.runtime.shuffle_search_combos
        self.next_short_break_at = 0.0
        self.throughput_window_seconds = max(60, config.runtime.throughput_window_minutes * 60)

        self.session_started_at = 0.0
        self.session_jobs_processed = 0
        self.session_jobs_submitted = 0
        self.session_jobs_attempted = 0
        self.circuit_breaker = AdaptiveCircuitBreaker(failure_threshold=5, cooldown_seconds=60.0)
        self.session_jobs_failed_attempts = 0
        self.session_jobs_failed_medical = 0
        self.submitted_timestamps: deque[float] = deque(maxlen=1000)
        self.stop_requested = False
        self.stop_reason: str | None = None

        self.debug_root = Path("debug")
        self.debug_failed_root = self.debug_root / "failed"
        self.debug_failed_root.mkdir(parents=True, exist_ok=True)
        self._cleanup_old_debug_snapshots(max_keep=50)

        self.first_job_debug_done = False
        self.current_job_id: str | None = None
        self.current_job_debug_dir: Path | None = None
        self.current_job_first_try_dir: Path | None = None
        self.current_job_debug_step = 0
        self.current_job_failure_count = 0
        self.qa_file: Path | None = None
        self.answers: dict[str, str] = {}

    def _cleanup_old_debug_snapshots(self, max_keep: int = 50) -> None:
        try:
            if not self.debug_failed_root.exists():
                return
            failed_dirs = sorted([d for d in self.debug_failed_root.iterdir() if d.is_dir()], key=lambda p: p.stat().st_mtime)
            if len(failed_dirs) > max_keep:
                for old_dir in failed_dirs[: len(failed_dirs) - max_keep]:
                    shutil.rmtree(old_dir, ignore_errors=True)
        except Exception as exc:
            log.debug(f"Debug snapshot cleanup skipped: {exc}")

    def _init_browser(self, config: AppConfig) -> None:
        self.options = build_browser_options(
            headless=config.runtime.headless,
            user_data_dir=config.runtime.user_data_dir,
            proxy=config.runtime.proxy,
        )
        chromedriver_path = shutil.which("chromedriver")
        chrome_path = detect_chrome_binary()
        if chrome_path:
            self.options.binary_location = chrome_path
        self.browser = build_webdriver(self.options, chromedriver_path)
        self.wait = WebDriverWait(self.browser, 30)

    def _init_services(self, config: AppConfig) -> None:
        self.relevance_scorer = RelevanceScorer()
        self.auto_answer = AutoAnswer(
            qa_file=self.qa_file,
            ans_yaml_path=Path(config.ans_yaml_path),
            salary=self.salary,
            hourly_rate=self.rate,
            answers=self.answers,
            log=log,
            linkedin_profile_url=config.linkedin_profile_url,
            full_name=config.full_name,
            first_name=config.first_name,
            last_name=config.last_name,
            form_email=config.form_email,
            phone_number=config.phone_number,
            github_url=config.github_url,
            location_city=config.location_city,
        )
        self.diagnostics = DiagnosticsService(self)
        self.questions = QuestionService(self)
        self.apply_flow = ApplyFlowService(self)
        self.throughput = ThroughputService(self)
        self.session = SessionService(self)

        if not self.restore_session_from_cookies():
            self.start_linkedin(config.username, config.password)

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
        try:
            if hasattr(self, "browser") and self.browser is not None:
                handles = self.browser.window_handles
                while len(handles) > 1:
                    self.browser.switch_to.window(handles[-1])
                    self.browser.close()
                    handles = self.browser.window_handles
                    self.browser.switch_to.window(handles[0])
        except Exception as exc:
            log.debug(f"Error cleaning up window handles: {exc}")
        self.diagnostics.finish_job_debug_trace()

    def _dump_debug_html(self, tag: str, force_dir: Path | None = None, extra: dict | None = None) -> None:
        self.diagnostics.dump_debug_html(tag, force_dir=force_dir, extra=extra)

    def _dump_failure_snapshot(self, reason: str, force_failed_root: bool = False) -> None:
        self.diagnostics.dump_failure_snapshot(reason, force_failed_root=force_failed_root)

    def _extract_job_metadata(self, job_id: str | None = None) -> dict:
        return self.diagnostics.extract_job_metadata(job_id=job_id)

    def _medical_keyword_match(self) -> str | None:
        return self.diagnostics.medical_keyword_match()

    def _coerce_numeric_answer(self, question: str, answer: str) -> str:
        return self.questions.coerce_numeric_answer(question, answer)

    def _normalize_text_answer(self, question: str, answer: str, input_id: str = "") -> str:
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

    def _update_session_throughput(self, *, reason: str, attempted: bool, result: bool) -> None:
        self.throughput.update_session_throughput(reason=reason, attempted=attempted, result=result)

    def start_linkedin(self, username: str, password: str) -> None:
        self.session.start_linkedin(username, password)

    def is_logged_in(self) -> bool:
        return self.session.is_logged_in()

    def restore_session_from_cookies(self) -> bool:
        return self.session.restore_session_from_cookies()

    def save_session_cookies(self) -> None:
        self.session.save_session_cookies()

    @staticmethod
    def get_applied_ids(filename: str) -> list[str] | None:
        return load_recent_applied_ids(filename)

    def fill_data(self) -> None:
        try:
            if not getattr(self.runtime, "headless", False):
                self.browser.maximize_window()
        except Exception:
            pass

    def _human_type(self, element, text: str) -> None:
        human_type_with_jitter(element, text)

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
        self.session_failed_ids.clear()
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
        combos = [(pos, loc) for pos in randomized_positions for loc in locations]
        if not combos:
            log.warning("No search combinations available.")
            return

        while not self.stop_requested and time.time() < self.session_deadline:
            if self.shuffle_search_combos:
                random.shuffle(combos)

            for position, location in combos:
                if self.stop_requested or time.time() >= self.session_deadline:
                    break
                self._maybe_take_short_break(source="combo_loop")
                log.info(f"Applying to {position}: {location}")
                self.log_event("combo_start", position=position, location=location)
                self.applications_loop(position, f"&location={location}")

            if not self.stop_requested and time.time() < self.session_deadline:
                self.session_failed_ids.clear()
                log.info("Finished all search combinations. Restarting search loop.")

        self.log_event("session_deadline_reached", stop_reason=self.stop_reason or "time_budget_exhausted")
        self._print_session_summary()

    def _print_session_summary(self) -> None:
        elapsed = max(1.0, time.time() - self.session_started_at)
        rate = (self.session_jobs_submitted / self.session_jobs_attempted * 100) if self.session_jobs_attempted > 0 else 0.0
        log.info("")
        log.info("=" * 60)
        log.info("                     SESSION SUMMARY                        ")
        log.info("=" * 60)
        log.info(f"  Duration:            {elapsed / 60:.1f} minutes")
        log.info(f"  Jobs Processed:      {self.session_jobs_processed}")
        log.info(f"  Attempts Started:    {self.session_jobs_attempted}")
        log.info(f"  Submitted:           {self.session_jobs_submitted}")
        log.info(f"  Failed Attempts:     {self.session_jobs_failed_attempts}")
        log.info(f"  Success Rate:        {rate:.1f}%")
        log.info(f"  Termination Reason:  {self.stop_reason or 'time_budget_exhausted'}")
        log.info("=" * 60)
        log.info("")

    def apply_to_job(self, job_id: str) -> bool:
        self._start_job_debug_trace(job_id)
        self._dump_debug_html("job_open_start")
        self.get_job_page(job_id)
        self._dump_debug_html("job_page_loaded")
        reading_pause(min_seconds=0.8, max_seconds=1.8)
        self._human_sleep(MICRO_PAUSE_SECONDS)

        if not self._matches_selected_experience_level():
            log.info(f"Skipping job {job_id}: experience level mismatch.")
            self.log_event("job_skipped_experience_level_mismatch", job_id=job_id, title=self.browser.title, selected_experience_level=self.experience_level)
            self._finish_job_debug_trace()
            return False

        button = self.get_easy_apply_button()
        self._dump_debug_html("easy_apply_button_detected", extra={"button_found": bool(button)})

        if self._is_daily_limit_reached():
            log.warning("LinkedIn daily application limit reached.")
            self.request_stop("daily_easy_apply_limit_reached", job_id=job_id)
            self.log_event("daily_limit_reached", job_id=job_id)
            self._finish_job_debug_trace()
            return False

        result, reason, string_easy = self._classify_job(job_id, button)
        return self._record_job_result(job_id, button, result, reason, string_easy)

    @staticmethod
    def _normalize_title_text(text: str) -> str:
        cleaned = (text or "").lower()
        for char in ("’", "‘", "`"):
            cleaned = cleaned.replace(char, "'")
        for char in ("—", "–", "_"):
            cleaned = cleaned.replace(char, "-")
        return f" {cleaned} "

    def is_title_blacklisted(self, title: str) -> tuple[bool, str | None]:
        normalized = self._normalize_title_text(title)
        for word in self.blacklist_titles:
            if self._normalize_title_text(word).strip() in normalized:
                return True, word
        for word in self.medical_related_keywords:
            if word.lower() in normalized:
                return True, word
        return False, None

    def _classify_job(self, job_id: str, button) -> tuple[bool, str, str]:
        if button is not False:
            normalized_title = self._normalize_title_text(self.browser.title)
            med = self._medical_keyword_match()
            if med:
                log.info(f"Skipping: medical-related keyword '{med}'.")
                self.log_event("job_skipped_medical_related", job_id=job_id, title=self.browser.title, matched_keyword=med)
                return False, "medical_related_title", "* Medical-related role skipped"

            bl = next((w for w in self.blacklist_titles if self._normalize_title_text(w).strip() in normalized_title), None)
            if bl:
                log.info(f"Skipping: blacklisted keyword '{bl}'.")
                self.log_event("job_skipped_title_blacklisted", job_id=job_id, title=self.browser.title, matched_keyword=bl)
                return False, "title_blacklisted", f"* Contains blacklisted keyword: {bl}"

            db = next((w for w in self.database_related_title_keywords if w.lower() in normalized_title), None)
            if db:
                log.info("Skipping: database-related keyword in title.")
                self.log_event("job_skipped_database_related_title", job_id=job_id, title=self.browser.title, matched_keyword=db)
                return False, "database_related_title", "* Contains database-related keyword"

            if hasattr(self, "relevance_scorer") and self.relevance_scorer is not None:
                title = self.browser.title or ""
                if not self.relevance_scorer.is_relevant(title):
                    score = self.relevance_scorer.score(title)
                    log.info(f"Skipping: low relevance ({score:.2f}) for '{title}'.")
                    self.log_event("job_skipped_not_relevant", job_id=job_id, title=title, relevance_score=score)
                    return False, "not_relevant", f"* Not relevant to resume (score={score:.2f})"

            metadata = self._extract_job_metadata(job_id=job_id) if hasattr(self, "_extract_job_metadata") else {}
            if hasattr(self, "auto_answer") and self.auto_answer is not None and hasattr(self.auto_answer, "set_current_job"):
                self.auto_answer.set_current_job(job_title=metadata.get("job_title", ""), company=metadata.get("company", ""))

            log.info("Clicking the EASY apply button")
            self._click_easy_apply(button)
            self._dump_debug_html("easy_apply_clicked")
            self._human_sleep(QUESTION_LOAD_PAUSE_SECONDS)
            self.fill_out_fields()
            result = self.send_resume()
            if result:
                return True, "submitted", "*Applied: Sent Resume"
            if self.stop_requested and self.stop_reason == "daily_easy_apply_limit_reached":
                return False, "daily_limit_reached", "*Stopped: LinkedIn Easy Apply daily limit reached"

            try:
                if "linkedin.com" not in (self.browser.current_url or "").lower():
                    self.browser.back()
                    time.sleep(MICRO_PAUSE_SECONDS)
            except Exception:
                pass
            return False, "apply_flow_failed", "*Did not apply: Failed to send Resume"

        if self._is_already_applied_job_page():
            log.info("Already applied to this position.")
            return False, "already_applied", "* Already Applied"

        log.info("The Easy apply button does not exist.")
        return False, "no_easy_apply_button", "* Doesn't have Easy Apply Button"

    def _record_job_result(self, job_id: str, button, result: bool, reason: str, string_easy: str) -> bool:
        log.info(f"\nPosition {job_id}:\n {self.browser.title} \n {string_easy} \n")
        metadata = self._extract_job_metadata(job_id=job_id)
        self.log_event("job_processed", attempted=bool(button), result=result, reason=reason, easy_apply_button=bool(button), **metadata)
        self.write_to_file(button, job_id, self.browser.title, result, metadata, reason)
        self._update_session_throughput(reason=reason, attempted=bool(button), result=result)

        if result:
            if hasattr(self, "circuit_breaker"):
                self.circuit_breaker.record_success()
        elif bool(button) and reason not in ("medical_related_title", "blacklisted_title", "blacklisted_company"):
            if hasattr(self, "circuit_breaker") and self.circuit_breaker.record_failure():
                cooldown = self.circuit_breaker.cooldown_seconds
                log.warning(f"Circuit breaker triggered. Anti-detection cooldown {cooldown}s...")
                self.log_event("circuit_breaker_cooldown", duration_seconds=cooldown)
                time.sleep(cooldown)

        if not result and reason != "daily_limit_reached":
            self._dump_failure_snapshot(f"job_result_{reason}", force_failed_root=(reason == "medical_related_title"))
        self._finish_job_debug_trace()
        return result

    def write_to_file(
        self, button, job_id, browser_title, result, metadata: dict | None = None, reason: str | None = None
    ) -> None:
        def re_extract(text, pattern):
            target = re.search(pattern, text)
            return target.group(1) if target else target

        timestamp = datetime.now().isoformat(timespec="seconds")
        attempted = button is not False
        job = None
        company = None
        if metadata:
            meta_title = metadata.get("job_title")
            meta_company = metadata.get("company")
            if meta_title and meta_title not in ("LinkedIn", "Unknown Role"):
                job = meta_title
            if meta_company and meta_company != "Unknown Company":
                company = meta_company

        if not job or not company:
            title_parts = [p.strip() for p in browser_title.split(" | ")] if browser_title else []
            if title_parts and title_parts[-1].lower() == "linkedin":
                title_parts = title_parts[:-1]
            if len(title_parts) >= 2:
                company_text = title_parts[-1]
                job_text = " | ".join(title_parts[:-1])
            elif len(title_parts) == 1:
                job_text = title_parts[0]
                company_text = "Unknown Company"
            else:
                job_text, company_text = "Unknown Role", "Unknown Company"

            if not job:
                job = re_extract(job_text, r"\(?\d?\)?\s?(\w.*)") or job_text
            if not company:
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
            if bool(result) or reason in (
                "already_applied", "title_blacklisted", "medical_related_title",
                "database_related_title", "not_relevant", "no_easy_apply_button",
                "blacklisted_title", "blacklisted_company",
            ):
                if job_id_str not in self.appliedJobIDs:
                    self.appliedJobIDs.append(job_id_str)
            else:
                if hasattr(self, "session_failed_ids"):
                    self.session_failed_ids.add(job_id_str)
            self.log_event("results_write_ok", results_json=self.results_filename, record=record)
        except Exception as exc:
            self.log_event("results_write_error", results_json=self.results_filename, error=str(exc), record=record)
            raise

    def get_job_page(self, job_id):
        self.browser.get(f"https://www.linkedin.com/jobs/view/{job_id}")
        self.job_page = self.load_page(sleep=0.02, scroll_limit=500)
        return self.job_page

    def _is_daily_limit_reached(self) -> bool:
        try:
            detected, _ = self.apply_flow.detect_daily_easy_apply_limit()
            return detected
        except Exception as exc:
            log.debug(f"Error checking daily limit: {exc}")
            return False

    def get_easy_apply_button(self):
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "button, a, a[role='button']")))
        except TimeoutException as exc:
            log.debug(f"Timeout waiting for Easy Apply button presence: {exc}")

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
            (By.XPATH, "//a[.//*[contains(normalize-space(), 'Easy Apply')] or contains(normalize-space(), 'Easy Apply')]"),
        ]
        candidates = []
        for by, value in selectors:
            try:
                candidates.extend(self.browser.find_elements(by, value))
            except Exception:
                continue

        seen_ids = set()
        for button in [c for c in candidates if c.id not in seen_ids and not seen_ids.add(c.id)]:
            try:
                aria = (button.get_attribute("aria-label") or "").lower()
                text = (button.text or "").strip().lower()
                if ("easy apply" in aria or "easy apply" in text) and button.is_displayed() and button.is_enabled():
                    return button
            except Exception:
                continue

        try:
            for button in self.browser.find_elements(By.CSS_SELECTOR, "button, a"):
                aria = (button.get_attribute("aria-label") or "").lower()
                text = (button.text or "").strip().lower()
                if ("easy apply" in aria or "easy apply" in text) and button.is_displayed() and button.is_enabled():
                    return button
        except Exception:
            pass
        return False

    def _click_easy_apply(self, element) -> None:
        is_link = False
        initial_url = ""
        raw_href = ""
        try:
            tag = (element.tag_name or "").lower()
            raw_href = (element.get_attribute("href") or "").strip()
            href_lower = raw_href.lower()
            is_link = tag == "a" or "/apply/" in href_lower or "opensduiapplyflow" in href_lower
            initial_url = self.browser.current_url or ""
        except Exception:
            pass

        try:
            self.browser.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", element)
        except Exception:
            pass
        time.sleep(CLICK_PAUSE_SECONDS * random.uniform(1.0, 1.8))

        strategies = ["action", "direct", "js"]
        random.shuffle(strategies)
        for strategy in strategies:
            try:
                if strategy == "action":
                    from selenium.webdriver.common.action_chains import ActionChains
                    ActionChains(self.browser).move_to_element(element).pause(random.uniform(0.06, 0.16)).click().perform()
                elif strategy == "direct":
                    element.click()
                else:
                    self.browser.execute_script("arguments[0].click();", element)
                break
            except Exception as exc:
                log.debug(f"Click strategy '{strategy}' failed: {exc}")

        try:
            if len(self.browser.window_handles) > 1:
                self.browser.switch_to.window(self.browser.window_handles[-1])
        except Exception:
            pass

        if is_link:
            try:
                WebDriverWait(self.browser, 4).until(
                    lambda d: (d.current_url != initial_url)
                    or ("/apply/" in (d.current_url or "").lower())
                    or (hasattr(self, "apply_flow") and self.apply_flow.has_apply_controls())
                    or (hasattr(self, "apply_flow") and self.apply_flow.find_easy_apply_modal() is not None)
                )
                self.load_page(sleep=MICRO_PAUSE_SECONDS, scroll_limit=300)
                reading_pause(min_seconds=0.4, max_seconds=0.8)
            except Exception as exc:
                log.debug(f"Post-click navigation wait for link-based Easy Apply: {exc}")

            # If click did not transition URL and no modal appeared, navigate directly to target href
            if raw_href and ("/apply/" in raw_href.lower() or "opensdui" in raw_href.lower()):
                try:
                    curr = self.browser.current_url or ""
                    modal = self.apply_flow.find_easy_apply_modal() if hasattr(self, "apply_flow") else None
                    if "/apply/" not in curr.lower() and modal is None:
                        log.info(f"Link click did not transition URL; navigating directly to apply href: {raw_href}")
                        self.browser.get(raw_href)
                        self.load_page(sleep=MICRO_PAUSE_SECONDS, scroll_limit=300)
                except Exception as exc:
                    log.debug(f"Direct apply href navigation failed: {exc}")

    def fill_out_fields(self):
        field_map = {
            "Mobile phone number": self.phone_number,
            "Email address": getattr(self.auto_answer, "form_email", ""),
            "First name": getattr(self.auto_answer, "first_name", ""),
            "Last name": getattr(self.auto_answer, "last_name", ""),
            "City": self.location_city,
            "LinkedIn Profile": getattr(self.auto_answer, "linkedin_profile_url", ""),
            "GitHub": getattr(self.auto_answer, "github_url", ""),
        }
        try:
            fields = self.browser.find_elements(By.CLASS_NAME, "jobs-easy-apply-form-section__grouping")
            for field in fields:
                field_text = field.text or ""
                for label, value in field_map.items():
                    if label in field_text and value:
                        try:
                            input_el = field.find_element(By.TAG_NAME, "input")
                            if not (input_el.get_attribute("value") or "").strip():
                                input_el.clear()
                                self._human_type(input_el, str(value))
                                self.log_event("contact_field_filled", field=label, value=str(value)[:20])
                        except Exception as exc:
                            log.debug(f"Failed to fill '{label}' field: {exc}")
                        break
        except Exception as exc:
            log.debug(f"Error inspecting form groupings: {exc}")

    def get_elements(self, element_type) -> list:
        element = self.locator[element_type]
        return self.browser.find_elements(element[0], element[1]) if self.is_present(element) else []

    def is_present(self, locator) -> bool:
        return len(self.browser.find_elements(locator[0], locator[1])) > 0

    def _safe_click(self, element) -> bool:
        try:
            self.browser.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
            time.sleep(CLICK_PAUSE_SECONDS)
            element.click()
            return True
        except Exception:
            pass
        try:
            self.browser.execute_script("arguments[0].click();", element)
            return True
        except Exception:
            return False

    def _find_clickable(self, selectors: Sequence[tuple[str, str]]):
        for by, value in selectors:
            try:
                for element in self.browser.find_elements(by, value):
                    if element.is_displayed() and element.is_enabled():
                        return element
            except Exception:
                continue
        return None

    def _select_non_default_option(self, select_element) -> bool:
        try:
            for option in select_element.find_elements(By.TAG_NAME, "option"):
                text = (option.text or "").strip().lower()
                value = (option.get_attribute("value") or "").strip().lower()
                if text and "select an option" not in text and value not in ("", "select an option"):
                    option.click()
                    return True
        except Exception:
            pass
        return False

    def _select_option_by_answer(self, select_element, answer: str) -> bool:
        ans_norm = (answer or "").strip().lower()
        if not ans_norm:
            return False
        try:
            options = select_element.find_elements(By.TAG_NAME, "option")
            for option in options:
                t, v = (option.text or "").strip().lower(), (option.get_attribute("value") or "").strip().lower()
                if t == ans_norm or v == ans_norm:
                    option.click()
                    return True
            for option in options:
                t, v = (option.text or "").strip().lower(), (option.get_attribute("value") or "").strip().lower()
                if ans_norm in t or ans_norm in v:
                    option.click()
                    return True
        except Exception:
            pass
        return False

    def _fill_typeahead_input(self, input_el, answer: str) -> bool:
        try:
            from selenium.webdriver.common.keys import Keys
            input_el.clear()
            input_el.send_keys(answer)
            time.sleep(TYPEAHEAD_PAUSE_SECONDS)
            for sel in (
                "div[role='option'].basic-typeahead__selectable", "[role='listbox'] [role='option']",
                "li[role='option']", "div.type-ahead-results__result", "div.artdeco-typeahead__result",
            ):
                visible = [o for o in self.browser.find_elements(By.CSS_SELECTOR, sel) if o.is_displayed()]
                if visible:
                    self.browser.execute_script("arguments[0].click();", visible[0])
                    return True
            input_el.send_keys(Keys.DOWN)
            time.sleep(0.2)
            input_el.send_keys(Keys.ENTER)
            return True
        except Exception as exc:
            log.debug(f"Fill typeahead failed for '{answer}': {exc}")
        return False

    def load_page(self, sleep: float = MICRO_PAUSE_SECONDS, scroll_limit: int = 1500, scroll_step: int = 400):
        if scroll_limit > 0:
            smooth_scroll_to(self.browser, scroll_limit, step_size=scroll_step, pause_sec=sleep)
            smooth_scroll_to(self.browser, 0, step_size=scroll_step, pause_sec=sleep)
        return BeautifulSoup(self.browser.page_source, "lxml")

    def avoid_lock(self) -> None:
        try:
            import pyautogui
            x, _ = pyautogui.position()
            pyautogui.moveTo(x + 200, pyautogui.position().y, duration=1.0)
            pyautogui.moveTo(x, pyautogui.position().y, duration=0.5)
            pyautogui.keyDown("ctrl")
            pyautogui.press("esc")
            pyautogui.keyUp("ctrl")
            time.sleep(MODAL_TRANSITION_PAUSE_SECONDS)
            pyautogui.press("esc")
        except Exception:
            pass

    def _human_sleep(self, base_seconds: float, variance: float = 0.2) -> None:
        time.sleep(base_seconds * random.uniform(1 - variance, 1 + variance))
