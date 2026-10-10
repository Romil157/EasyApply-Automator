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
    _seen_session_job_ids: set[str]

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

        consecutive_empty_pages = 0
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
                    if scroll_results:
                        try:
                            self.browser.execute_script(
                                "if (arguments[0]) { for (let i = 300; i <= 3000; i += 200) { arguments[0].scrollTo(0, i); } }",
                                scroll_results[0],
                            )
                        except Exception:
                            for i in range(300, 3000, 200):
                                self.browser.execute_script(
                                    f"arguments[0].scrollTo(0, {i})", scroll_results[0]
                                )

                cards_batch = self.extract_job_cards_batch()
                if cards_batch:
                    consecutive_empty_pages = 0
                    self.apply_loop_batch(cards_batch)
                else:
                    job_ids = self.extract_job_card_ids()
                    if job_ids:
                        consecutive_empty_pages = 0
                        self.apply_loop(job_ids)
                    else:
                        consecutive_empty_pages += 1

                pages_processed += 1
                if consecutive_empty_pages >= 2:
                    self.log_event(
                        "combo_no_results",
                        position=position,
                        location=location,
                        pages_processed=pages_processed,
                    )
                    log.info(
                        f"No more job results found for '{position}' in '{location}' "
                        f"after {consecutive_empty_pages} consecutive empty pages. Moving to next search combination."
                    )
                    break
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

    def extract_job_card_ids(self) -> dict[str, str]:
        """Extracts job IDs from all visible LinkedIn job cards using multi-selector fallback."""
        job_ids: dict[str, str] = {}
        seen_ids: set[str] = set()

        card_selectors = [
            (By.CSS_SELECTOR, "li.jobs-search-results__list-item"),
            (By.CSS_SELECTOR, "div.job-card-container"),
            (By.CSS_SELECTOR, "[data-occludable-job-id]"),
            (By.CSS_SELECTOR, "[data-job-id]"),
            (By.CSS_SELECTOR, "div.job-card-list"),
            (By.XPATH, "//div[@data-job-id]"),
        ]

        raw_elements = []
        for by, val in card_selectors:
            try:
                found = self.browser.find_elements(by, val)
                if found:
                    raw_elements.extend(found)
            except Exception:
                continue

        for el in raw_elements:
            try:
                text = (el.text or "").strip()
                if "Applied" in text or (text and text in self.blacklist):
                    continue

                jid = (
                    el.get_attribute("data-job-id")
                    or el.get_attribute("data-occludable-job-id")
                    or el.get_attribute("data-entity-urn")
                    or ""
                ).strip()

                if not jid or jid == "search" or not jid.isdigit():
                    try:
                        links = el.find_elements(
                            By.CSS_SELECTOR, "a[href*='/jobs/view/'], a[data-job-id]"
                        )
                        for link_el in links:
                            sub_jid = link_el.get_attribute("data-job-id") or ""
                            if sub_jid and sub_jid.isdigit():
                                jid = sub_jid
                                break
                            href = link_el.get_attribute("href") or ""
                            m = re.search(r"/jobs/view/(\d+)", href)
                            if m:
                                jid = m.group(1)
                                break
                    except Exception:
                        pass

                if jid and jid.isdigit() and jid not in seen_ids:
                    seen_ids.add(jid)
                    job_ids[jid] = "To be processed"
            except Exception:
                continue

        if not job_ids:
            try:
                anchors = self.browser.find_elements(By.CSS_SELECTOR, "a[href*='/jobs/view/']")
                for a in anchors:
                    href = a.get_attribute("href") or ""
                    m = re.search(r"/jobs/view/(\d+)", href)
                    if m:
                        jid = m.group(1)
                        if jid not in seen_ids:
                            seen_ids.add(jid)
                            job_ids[jid] = "To be processed"
            except Exception:
                pass

        return job_ids

    def _extract_title_from_card(self, card) -> str:
        card_title = ""
        for sel in (
            "a.job-card-list__title",
            "a.job-card-container__link",
            ".job-card-list__title--link",
            "strong",
        ):
            try:
                el = card.find_element(By.CSS_SELECTOR, sel)
                text = (el.text or "").strip()
                if text and len(text) > 2:
                    card_title = text
                    break
            except Exception:
                continue

        if not card_title:
            return ""

        company = ""
        for comp_sel in (
            ".job-card-container__primary-description",
            ".artdeco-entity-lockup__subtitle",
            ".job-card-list__company-name",
            ".job-card-container__company-name",
        ):
            try:
                c_el = card.find_element(By.CSS_SELECTOR, comp_sel)
                c_text = (c_el.text or "").strip()
                if c_text:
                    company = c_text
                    break
            except Exception:
                continue
        return f"{card_title} | {company}" if (company and company != card_title) else card_title

    def _extract_card_titles(self) -> dict[str, str]:
        """Extract mapping of job_id -> title from visible search result cards."""
        titles: dict[str, str] = {}
        try:
            cards = self.browser.find_elements(
                By.CSS_SELECTOR,
                "li.jobs-search-results__list-item, div.job-card-container, div[data-job-id], [data-occludable-job-id]",
            )
            for card in cards:
                try:
                    job_id = (
                        card.get_attribute("data-job-id")
                        or card.get_attribute("data-occludable-job-id")
                        or card.get_attribute("data-entity-urn")
                        or ""
                    ).strip()
                    if not job_id or not job_id.isdigit():
                        link_el = card.find_elements(
                            By.CSS_SELECTOR, "a[data-job-id], a[href*='/jobs/view/']"
                        )
                        if link_el:
                            sub_jid = link_el[0].get_attribute("data-job-id") or ""
                            if sub_jid and sub_jid.isdigit():
                                job_id = sub_jid
                            else:
                                href = link_el[0].get_attribute("href") or ""
                                m = re.search(r"/jobs/view/(\d+)", href)
                                if m:
                                    job_id = m.group(1)
                    if not job_id or not job_id.isdigit() or str(job_id) in titles:
                        continue
                    card_title = self._extract_title_from_card(card)
                    if card_title:
                        titles[str(job_id)] = card_title
                except Exception:
                    continue
        except Exception as exc:
            log.debug(f"Failed to extract card titles from search page: {exc}")
        return titles

    def _lookup_card_title(self, job_id: str) -> str:
        """Attempt to find title for a specific job_id on the search results page."""
        try:
            selectors = [
                f"[data-job-id='{job_id}']",
                f"[data-occludable-job-id='{job_id}']",
                f"a[data-job-id='{job_id}']",
                f"a[href*='/jobs/view/{job_id}']",
            ]
            for sel in selectors:
                elements = self.browser.find_elements(By.CSS_SELECTOR, sel)
                for el in elements:
                    card = el
                    try:
                        parent = el.find_element(
                            By.XPATH,
                            "./ancestor-or-self::*[contains(@class, 'job-card') or contains(@class, 'jobs-search-results__list-item')][1]",
                        )
                        if parent:
                            card = parent
                    except Exception:
                        pass
                    title = self._extract_title_from_card(card)
                    if title:
                        return title
        except Exception:
            pass
        return ""

    def extract_job_cards_batch(self) -> list[dict[str, Any]]:
        """Extracts job card metadata (id, title, company, applied, easy_apply) in a single JS call."""
        try:
            raw_cards = self.browser.execute_script(
                """
                return (function() {
                    const cards = document.querySelectorAll(
                        "li.jobs-search-results__list-item, div.job-card-container, div[data-job-id], [data-occludable-job-id], div.job-card-list"
                    );
                    const results = [];
                    const seen = new Set();
                    for (let i = 0; i < cards.length; i++) {
                        const card = cards[i];
                        let jid = (
                            card.getAttribute("data-job-id") ||
                            card.getAttribute("data-occludable-job-id") ||
                            card.getAttribute("data-entity-urn") ||
                            ""
                        ).trim();
                        if (!jid || !/^\\d+$/.test(jid)) {
                            const link = card.querySelector("a[data-job-id], a[href*='/jobs/view/']");
                            if (link) {
                                const subJid = (link.getAttribute("data-job-id") || "").trim();
                                if (/^\\d+$/.test(subJid)) {
                                    jid = subJid;
                                } else {
                                    const href = link.getAttribute("href") || "";
                                    const m = href.match(/\\/jobs\\/view\\/(\\d+)/);
                                    if (m) jid = m[1];
                                }
                            }
                        }
                        if (!jid || !/^\\d+$/.test(jid) || seen.has(jid)) continue;
                        seen.add(jid);

                        let title = "";
                        const titleEl = card.querySelector("a.job-card-list__title, a.job-card-container__link, .job-card-list__title--link, strong");
                        if (titleEl) {
                            title = (titleEl.innerText || titleEl.textContent || "").trim();
                        }

                        let company = "";
                        const compEl = card.querySelector(".job-card-container__primary-description, .artdeco-entity-lockup__subtitle, .job-card-list__company-name, .job-card-container__company-name");
                        if (compEl) {
                            company = (compEl.innerText || compEl.textContent || "").trim();
                        }

                        const text = (card.innerText || card.textContent || "").trim();
                        const applied = text.includes("Applied");
                        const hasEasyApply = text.includes("Easy Apply") || !!card.querySelector("[aria-label*='Easy Apply'], .job-card-container__apply-method");

                        results.push({
                            job_id: jid,
                            title: title,
                            company: company,
                            applied: applied,
                            has_easy_apply: hasEasyApply
                        });
                    }
                    return results;
                })();
                """
            )
            if isinstance(raw_cards, list) and raw_cards:
                return raw_cards
        except Exception as exc:
            log.debug(f"Batch job card extraction via JS failed or unsupported: {exc}")
        return []

    def apply_loop_batch(self, cards: list[dict[str, Any]]) -> None:
        """High-throughput apply loop processing pre-extracted job cards with zero extra DOM queries."""
        if not hasattr(self, "_seen_session_job_ids"):
            self._seen_session_job_ids = set()

        perf_mode = (
            getattr(getattr(self, "config", None), "performance_mode", None)
            or getattr(self, "performance_mode", None)
        )
        skip_non_easy_apply = getattr(perf_mode, "skip_non_easy_apply_cards", True) if perf_mode else True

        for card in cards:
            if self.stop_requested or time.time() >= self.session_deadline:
                break

            max_apps = getattr(self, "max_applications", 0)
            submitted_count = getattr(self, "session_jobs_submitted", 0)
            if max_apps > 0 and submitted_count >= max_apps:
                log.info(f"Target application cap of {max_apps} reached. Ending session.")
                if hasattr(self, "request_stop"):
                    self.request_stop("max_applications_reached", max_applications=max_apps)
                break

            job_id = card.get("job_id", "")
            if not job_id:
                continue

            # In-memory session deduplication
            if job_id in self._seen_session_job_ids:
                log.debug(f"Job {job_id} already processed in current session. Skipping.")
                continue
            self._seen_session_job_ids.add(job_id)

            if card.get("applied", False):
                self.log_event("job_skipped_seen_recently", job_id=job_id, reason="card_shows_applied")
                continue

            if job_id in self.appliedJobIDs:
                self.log_event("job_skipped_seen_recently", job_id=job_id, reason="already_in_recent_results")
                continue

            if hasattr(self, "session_failed_ids") and job_id in self.session_failed_ids:
                self.log_event("job_skipped_seen_recently", job_id=job_id, reason="failed_earlier_in_session")
                continue

            title = card.get("title", "")
            company = card.get("company", "")
            card_title = f"{title} | {company}" if (company and company != title) else title

            # Check blacklist for company or raw title text
            if title and title in self.blacklist:
                self.log_event("job_skipped_seen_recently", job_id=job_id, reason="title_in_blacklist")
                continue
            if company and company in self.blacklist:
                self.log_event("job_skipped_seen_recently", job_id=job_id, reason="company_in_blacklist")
                continue

            # Check non-easy-apply prefilter
            if skip_non_easy_apply and not card.get("has_easy_apply", True) and card_title:
                log.info(f"Pre-filter skipping job {job_id} ('{card_title}'): card does not show Easy Apply badge.")
                self.log_event("job_skipped_prefilter", job_id=job_id, title=card_title, reason="not_easy_apply")
                continue

            if card_title:
                if hasattr(self, "is_title_blacklisted"):
                    is_blocked, keyword = self.is_title_blacklisted(card_title)
                    if is_blocked:
                        log.info(f"Pre-filter skipping job {job_id} ('{card_title}'): matched blacklist keyword '{keyword}'.")
                        self.log_event("job_skipped_prefilter", job_id=job_id, title=card_title, matched_keyword=keyword)
                        continue

                role_title = card_title.split(" | ")[0] if " | " in card_title else card_title
                if hasattr(self, "relevance_scorer") and self.relevance_scorer is not None:
                    if not self.relevance_scorer.is_relevant(role_title):
                        score = self.relevance_scorer.score(role_title)
                        log.info(f"Pre-filter skipping job {job_id} ('{card_title}'): low relevance score ({score:.2f}).")
                        self.log_event("job_skipped_not_relevant", job_id=job_id, title=card_title, relevance_score=score)
                        continue

            applied = self.apply_to_job(job_id)
            last_reason = getattr(self, "last_job_reason", None)
            if applied:
                log.info(f"Applied to {job_id}")
            elif last_reason in (
                "similar_jobs_redirect",
                "title_blacklisted",
                "blacklisted_title",
                "not_relevant",
                "medical_related_title",
                "already_applied",
                "experience_level_mismatch",
            ):
                log.info(f"Skipped {job_id} ({last_reason})")
            else:
                log.info(f"Failed to apply to {job_id}")

            if self.stop_requested or time.time() >= self.session_deadline:
                break

    def apply_loop(self, job_ids: dict[str, str]) -> None:
        if not hasattr(self, "_seen_session_job_ids"):
            self._seen_session_job_ids = set()

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
                if job_id in self._seen_session_job_ids:
                    log.debug(f"Job {job_id} already processed in current session. Skipping.")
                    job_ids[job_id] = "Skipped"
                    continue
                self._seen_session_job_ids.add(job_id)

                if job_id in self.appliedJobIDs:
                    self.log_event(
                        "job_skipped_seen_recently",
                        job_id=job_id,
                        reason="already_in_recent_results",
                    )
                    job_ids[job_id] = "Skipped"
                    continue

                if hasattr(self, "session_failed_ids") and job_id in self.session_failed_ids:
                    self.log_event(
                        "job_skipped_seen_recently",
                        job_id=job_id,
                        reason="failed_earlier_in_session",
                    )
                    job_ids[job_id] = "Skipped"
                    continue

                card_title = card_titles.get(job_id, "")
                if not card_title:
                    card_title = self._lookup_card_title(job_id)
                    if card_title:
                        card_titles[job_id] = card_title
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
                                job_id=job_id,
                                title=card_title,
                                matched_keyword=keyword,
                            )
                            job_ids[job_id] = "Skipped"
                            continue

                    # Pre-check relevance score before loading page
                    role_title = card_title.split(" | ")[0] if " | " in card_title else card_title
                    if hasattr(self, "relevance_scorer") and self.relevance_scorer is not None:
                        if not self.relevance_scorer.is_relevant(role_title):
                            score = self.relevance_scorer.score(role_title)
                            log.info(
                                f"Pre-filter skipping job {job_id} ('{card_title}'): "
                                f"low relevance score ({score:.2f})."
                            )
                            self.log_event(
                                "job_skipped_not_relevant",
                                job_id=job_id,
                                title=card_title,
                                relevance_score=score,
                            )
                            job_ids[job_id] = "Skipped"
                            continue

                applied = self.apply_to_job(job_id)
                last_reason = getattr(self, "last_job_reason", None)
                if applied:
                    log.info(f"Applied to {job_id}")
                    job_ids[job_id] = "Applied"
                elif last_reason in (
                    "similar_jobs_redirect",
                    "title_blacklisted",
                    "blacklisted_title",
                    "not_relevant",
                    "medical_related_title",
                    "already_applied",
                    "experience_level_mismatch",
                ):
                    log.info(f"Skipped {job_id} ({last_reason})")
                    job_ids[job_id] = "Skipped"
                else:
                    log.info(f"Failed to apply to {job_id}")
                    job_ids[job_id] = "Failed"
                if self.stop_requested or time.time() >= self.session_deadline:
                    break

    _DATE_MAP: dict[str, str] = {
        "past_24h": "r86400", "24h": "r86400", "r86400": "r86400",
        "past_week": "r604800", "week": "r604800", "r604800": "r604800",
        "past_month": "r2592000", "month": "r2592000", "r2592000": "r2592000",
    }
    _WP_MAP: dict[str, str] = {
        "onsite": "1", "on-site": "1", "1": "1",
        "remote": "2", "2": "2",
        "hybrid": "3", "3": "3",
    }
    _JT_MAP: dict[str, str] = {
        "full_time": "F", "full-time": "F", "fulltime": "F", "f": "F",
        "part_time": "P", "part-time": "P", "p": "P",
        "contract": "C", "c": "C",
        "internship": "I", "i": "I",
        "temporary": "T", "t": "T",
    }

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
            "f_AL": "true",
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

        date_filter = (getattr(self, "date_posted", "") or "").lower()
        if date_filter in self._DATE_MAP:
            params["f_TPR"] = self._DATE_MAP[date_filter]

        wp_codes = [self._WP_MAP[str(w).strip().lower()] for w in (getattr(self, "workplace_types", []) or []) if str(w).strip().lower() in self._WP_MAP]
        if wp_codes:
            params["f_WT"] = ",".join(dict.fromkeys(wp_codes))

        jt_codes = [self._JT_MAP[str(j).strip().lower()] for j in (getattr(self, "job_types", []) or []) if str(j).strip().lower() in self._JT_MAP]
        if jt_codes:
            params["f_JT"] = ",".join(dict.fromkeys(jt_codes))

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

        title = (getattr(self.browser, "title", "") or "").lower()
        senior_markers = (
            "senior",
            "sr",
            "lead",
            "principal",
            "staff",
            "director",
            "vp",
            "vice president",
            "head of",
            "manager",
            "chief",
            "team lead",
        )

        # If applying strictly to internships or entry level, block explicit senior titles
        if set(self.experience_level).issubset({1, 2}):
            for marker in senior_markers:
                if re.search(rf"\b{re.escape(marker)}\b", title):
                    return False

        return True
