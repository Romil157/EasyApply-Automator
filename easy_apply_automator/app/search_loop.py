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

    def _extract_card_titles(self) -> dict[str, str]:
        """Extract mapping of job_id -> title from visible search result cards."""
        titles: dict[str, str] = {}
        try:
            cards = self.browser.find_elements(
                By.CSS_SELECTOR,
                "li.jobs-search-results__list-item, div.job-card-container, div[data-job-id]",
            )
            for card in cards:
                try:
                    job_id = card.get_attribute("data-job-id") or ""
                    if not job_id:
                        try:
                            link = card.find_element(By.CSS_SELECTOR, "a[data-job-id]")
                            job_id = link.get_attribute("data-job-id") or ""
                        except Exception:
                            continue
                    if not job_id:
                        continue

                    for sel in (
                        ".job-card-list__title strong",
                        ".job-card-list__title",
                        ".artdeco-entity-lockup__title",
                        "a.job-card-container__link strong",
                        "a strong",
                    ):
                        try:
                            el = card.find_element(By.CSS_SELECTOR, sel)
                            text = (el.text or "").strip()
                            if text and len(text) > 2:
                                titles[str(job_id)] = text
                                break
                        except Exception:
                            continue
                except Exception:
                    continue
        except Exception as exc:
            log.debug(f"Failed to extract card titles from search page: {exc}")
        return titles

    def apply_loop(self, job_ids: dict[str, str]) -> None:
        card_titles = self._extract_card_titles()

        for job_id in job_ids:
            if self.stop_requested or time.time() >= self.session_deadline:
                break

            max_apps = getattr(self, "max_applications", 0)
            submitted_count = getattr(self, "session_jobs_submitted", 0)
            if max_apps > 0 and submitted_count >= max_apps:
                log.info(f"Target application cap of {max_apps} reached. Ending session.")
                if hasattr(self, "request_stop"):
                    self.request_stop("max_applications_reached", max_applications=max_apps)
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

                card_title = card_titles.get(str(job_id), "")
                if card_title:
                    # Pre-check blacklist before loading the full job page
                    if hasattr(self, "is_title_blacklisted"):
                        is_blocked, keyword = self.is_title_blacklisted(card_title)
                        if is_blocked:
                            log.info(
                                f"Pre-filter skipping job {job_id} ('{card_title}'): "
                                f"matched blacklist keyword '{keyword}'."
                            )
                            self.log_event(
                                "job_skipped_prefilter",
                                job_id=str(job_id),
                                title=card_title,
                                matched_keyword=keyword,
                            )
                            job_ids[job_id] = "Skipped"
                            continue

                    # Pre-check relevance score before loading page
                    if hasattr(self, "relevance_scorer") and self.relevance_scorer is not None:
                        if not self.relevance_scorer.is_relevant(card_title):
                            score = self.relevance_scorer.score(card_title)
                            log.info(
                                f"Pre-filter skipping job {job_id} ('{card_title}'): "
                                f"low relevance score ({score:.2f})."
                            )
                            self.log_event(
                                "job_skipped_not_relevant",
                                job_id=str(job_id),
                                title=card_title,
                                relevance_score=score,
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

    def build_search_url(
        self,
        position: str,
        location: str,
        jobs_per_page: int,
        experience_level: list[int] | None = None,
    ) -> str:
        """Constructs an advanced LinkedIn search URL incorporating all configured search filters."""
        import urllib.parse

        params: dict[str, str] = {
            "f_LF": "f_AL",
            "keywords": position,
            "start": str(jobs_per_page),
        }
        if location:
            loc_clean = location.lstrip("&location=")
            if loc_clean:
                params["location"] = loc_clean

        # Experience levels (e.g. 1=intern, 2=entry, 3=associate)
        exp_levels = experience_level or getattr(self, "experience_level", [])
        if exp_levels:
            params["f_E"] = ",".join(map(str, exp_levels))

        # Date posted filter
        date_filter = getattr(self, "date_posted", "") or ""
        date_map = {
            "past_24h": "r86400",
            "24h": "r86400",
            "r86400": "r86400",
            "past_week": "r604800",
            "week": "r604800",
            "r604800": "r604800",
            "past_month": "r2592000",
            "month": "r2592000",
            "r2592000": "r2592000",
        }
        if date_filter.lower() in date_map:
            params["f_TPR"] = date_map[date_filter.lower()]

        # Workplace types (1=On-site, 2=Remote, 3=Hybrid)
        wp_types = getattr(self, "workplace_types", []) or []
        wp_codes = []
        wp_map = {
            "onsite": "1",
            "on-site": "1",
            "remote": "2",
            "hybrid": "3",
            "1": "1",
            "2": "2",
            "3": "3",
        }
        for w in wp_types:
            code = wp_map.get(str(w).strip().lower())
            if code and code not in wp_codes:
                wp_codes.append(code)
        if wp_codes:
            params["f_WT"] = ",".join(wp_codes)

        # Job types (F=Full-time, P=Part-time, C=Contract, T=Temporary, I=Internship)
        job_types = getattr(self, "job_types", []) or []
        jt_codes = []
        jt_map = {
            "full_time": "F",
            "full-time": "F",
            "fulltime": "F",
            "f": "F",
            "part_time": "P",
            "part-time": "P",
            "p": "P",
            "contract": "C",
            "c": "C",
            "internship": "I",
            "i": "I",
            "temporary": "T",
            "t": "T",
        }
        for j in job_types:
            code = jt_map.get(str(j).strip().lower())
            if code and code not in jt_codes:
                jt_codes.append(code)
        if jt_codes:
            params["f_JT"] = ",".join(jt_codes)

        return f"https://www.linkedin.com/jobs/search/?{urllib.parse.urlencode(params)}"

    def next_jobs_page(self, position, location, jobs_per_page: int, experience_level=None):
        search_url = self.build_search_url(position, location, jobs_per_page, experience_level)
        self.browser.get(search_url)
        log.info(f"Loading jobs page (start={jobs_per_page}): {search_url}")
        self.load_page()
        return self.browser, jobs_per_page + 25

    def _matches_selected_experience_level(self) -> bool:
        if not self.experience_level or set(self.experience_level) == {1, 2, 3}:
            return True

        title = (self.browser.title or "").lower()
        senior_markers = (
            "senior ",
            "sr. ",
            "sr ",
            "lead ",
            "principal ",
            "staff ",
            "director ",
            "vp ",
            "vice president",
            "head of ",
            "manager ",
            "chief ",
            "team lead",
        )

        # If applying strictly to internships or entry level, block explicit senior titles
        if set(self.experience_level).issubset({1, 2}):
            if any(marker in title for marker in senior_markers):
                return False

        return True
