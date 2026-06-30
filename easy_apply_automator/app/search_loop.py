from __future__ import annotations

import random
import re
import time
from typing import Any

from selenium.webdriver.common.by import By

from easy_apply_automator.config.timing import PAGE_LOAD_PAUSE_SECONDS
from easy_apply_automator.observability.logger import log


class SearchLoopMixin:
    browser: Any
    experience_level: list[int]
    stop_requested: bool
    session_deadline: float
    max_pages_per_search: int
    blacklist: list[str]
    appliedJobIDs: list[str]
    locator: dict[str, tuple[str, str]]

    def _maybe_take_short_break(self, source: str) -> None:
        pass

    def log_event(self, event: str, **kwargs) -> None:
        pass

    def load_page(
        self, sleep: float = 0.1, scroll_limit: int = 1500, scroll_step: int = 500
    ) -> Any:
        return None

    def is_present(self, locator: tuple) -> bool:
        return False

    def get_elements(self, element_type: str) -> list:
        return []

    def apply_to_job(self, job_id: str) -> bool:
        return False

    def applications_loop(self, position: str, location: str) -> None:
        jobs_per_page = 0
        pages_processed = 0
        log.info("Looking for jobs.. Please wait..")

        try:
            self.browser.set_window_position(1, 1)
            self.browser.maximize_window()
        except Exception:
            try:
                self.browser.maximize_window()
            except Exception:
                pass
        self.browser, _ = self.next_jobs_page(
            position, location, jobs_per_page, experience_level=self.experience_level
        )
        log.info("Looking for jobs.. Please wait..")

        while (
            not self.stop_requested
            and time.time() < self.session_deadline
            and pages_processed < self.max_pages_per_search
        ):
            try:
                self._maybe_take_short_break(source="applications_loop")
                remaining_seconds = max(0, int(self.session_deadline - time.time()))
                remaining_minutes = round(remaining_seconds / 60, 2)
                log.info(f"{remaining_minutes} minutes left in this session")
                self.log_event(
                    "session_tick",
                    position=position,
                    location=location,
                    minutes_left=remaining_minutes,
                    jobs_page_start=jobs_per_page,
                )

                random_sleep = random.uniform(1.5, 2.9)
                log.debug(f"Sleeping for {round(random_sleep, 1)}")
                self.load_page(sleep=0.05, scroll_limit=1000)

                if self.is_present(self.locator["search"]):
                    scroll_results = self.get_elements("search")
                    for i in range(300, 3000, 100):
                        self.browser.execute_script(
                            f"arguments[0].scrollTo(0, {i})", scroll_results[0]
                        )

                if self.is_present(self.locator["links"]):
                    links = self.get_elements("links")
                    job_ids: dict[str, str] = {}
                    for link in links:
                        if "Applied" in link.text:
                            continue
                        if link.text in self.blacklist:
                            continue
                        job_id = link.get_attribute("data-job-id")
                        if job_id == "search":
                            log.debug(
                                f"Job ID not found, search keyword found instead? {link.text}"
                            )
                            continue
                        job_ids[job_id] = "To be processed"

                    if job_ids:
                        self.apply_loop(job_ids)
                    pages_processed += 1
                    if pages_processed >= self.max_pages_per_search:
                        self.log_event(
                            "combo_page_cap_reached",
                            position=position,
                            location=location,
                            pages_processed=pages_processed,
                            max_pages_per_search=self.max_pages_per_search,
                        )
                        break
                    self.browser, jobs_per_page = self.next_jobs_page(
                        position,
                        location,
                        jobs_per_page,
                        experience_level=self.experience_level,
                    )
                else:
                    pages_processed += 1
                    if pages_processed >= self.max_pages_per_search:
                        self.log_event(
                            "combo_page_cap_reached",
                            position=position,
                            location=location,
                            pages_processed=pages_processed,
                            max_pages_per_search=self.max_pages_per_search,
                        )
                        break
                    self.browser, jobs_per_page = self.next_jobs_page(
                        position,
                        location,
                        jobs_per_page,
                        experience_level=self.experience_level,
                    )
            except Exception as exc:
                error_message = str(exc)
                log.error(f"applications_loop error: {error_message}")
                self.log_event(
                    "applications_loop_error",
                    position=position,
                    location=location,
                    jobs_page_start=jobs_per_page,
                    error=error_message,
                )
                time.sleep(PAGE_LOAD_PAUSE_SECONDS)

    def apply_loop(self, job_ids: dict[str, str]) -> None:
        for job_id in job_ids:
            if self.stop_requested or time.time() >= self.session_deadline:
                break
            if job_ids[job_id] == "To be processed":
                if str(job_id) in self.appliedJobIDs:
                    self.log_event(
                        "job_skipped_seen_recently",
                        job_id=str(job_id),
                        reason="already_in_recent_results",
                    )
                    job_ids[job_id] = "Skipped"
                    continue
                applied = self.apply_to_job(job_id)
                if applied:
                    log.info(f"Applied to {job_id}")
                else:
                    log.info(f"Failed to apply to {job_id}")
                job_ids[job_id] = "Applied" if applied else "Failed"
                if self.stop_requested or time.time() >= self.session_deadline:
                    break

    def next_jobs_page(self, position, location, jobs_per_page: int, experience_level=None):
        experience_level = experience_level or []
        experience_level_str = ",".join(map(str, experience_level)) if experience_level else ""
        experience_level_param = f"&f_E={experience_level_str}" if experience_level_str else ""
        self.browser.get(
            "https://www.linkedin.com/jobs/search/?f_LF=f_AL&keywords="
            + position
            + location
            + "&start="
            + str(jobs_per_page)
            + experience_level_param
        )
        log.info("Loading next job page?")
        self.load_page()
        return self.browser, jobs_per_page + 25

    def _matches_selected_experience_level(self) -> bool:
        if not self.experience_level or set(self.experience_level) == {1, 2, 3}:
            return True

        title = (self.browser.title or "").lower()

        insights_text = ""
        selectors = [
            ".jobs-unified-top-card__job-insight",
            ".job-details-jobs-unified-top-card__job-insight",
            "span.jobs-unified-top-card__bullet-item",
            ".jobs-unified-top-card__bullet-item",
        ]
        for selector in selectors:
            try:
                elements = self.browser.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed() and el.text:
                        insights_text += " " + el.text.lower()
            except Exception:
                pass

        is_internship = bool(re.search(r"\bintern\b|\binternship\b", title)) or bool(
            re.search(r"\bintern\b|\binternship\b", insights_text)
        )

        if self.experience_level == [1]:
            return is_internship

        if 1 not in self.experience_level:
            return not is_internship

        return True
