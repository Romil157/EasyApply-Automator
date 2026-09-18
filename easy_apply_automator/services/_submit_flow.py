# This is an internal module intended for mixin implementation only.
# Do not import it directly; use ApplyFlowService instead.
from __future__ import annotations

import re
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from selenium.webdriver.common.by import By

from easy_apply_automator.config.timing import (
    CLICK_PAUSE_SECONDS,
    MICRO_PAUSE_SECONDS,
    POLL_INTERVAL_SECONDS,
    STATE_MACHINE_PAUSE_SECONDS,
)
from easy_apply_automator.observability.logger import log

if TYPE_CHECKING:
    from easy_apply_automator.app.orchestrator import LinkedInEasyApplyOrchestrator


class SubmitFlowMixin:
    bot: LinkedInEasyApplyOrchestrator

    EXTERNAL_ATS_DOMAINS: tuple[str, ...] = (
        "workday.com", "myworkday", "greenhouse.io", "boards.greenhouse.io",
        "lever.co", "jobs.lever.co", "smartrecruiters.com", "icims.com",
        "taleo.", "apply.workable.com", "bamboohr.com", "jobs.ashbyhq.com",
        "recruitee.com", "jazz.co", "jobvite.com", "ultipro.com",
        "successfactors.", "breezy.hr", "rippling.com",
    )

    def detect_daily_easy_apply_limit(self) -> tuple[bool, str | None]:
        try:
            page_source = (self.bot.browser.page_source or "").replace("’", "'").lower()
            markers = (
                "you reached today's easy apply limit", "you reached todays easy apply limit",
                "we limit easy apply submissions", "continue applying tomorrow",
                "easyapplyfuselimitdialogmodal", '"jobapplicationlimitreached":true',
            )
            for marker in markers:
                if marker in page_source:
                    return True, marker
        except Exception as exc:
            log.debug(f"Failed to check page source for daily limit: {exc}")

        try:
            dialogs = self.bot.browser.find_elements(By.CSS_SELECTOR, "dialog[open], [role='dialog'], div[data-test-modal]")
            for dialog in dialogs:
                if not dialog.is_displayed():
                    continue
                d_text = " ".join(filter(None, (
                    dialog.text or "",
                    dialog.get_attribute("data-sdui-screen") or "",
                    dialog.get_attribute("aria-label") or "",
                ))).replace("’", "'").lower()
                if "easyapplyfuselimitdialogmodal" in d_text:
                    return True, "dialog_screen"
                if "easy apply limit" in d_text and any(k in d_text for k in ("today", "tomorrow", "continue applying")):
                    return True, "dialog_text"
        except Exception as exc:
            log.debug(f"Daily limit dialog check failed: {exc}")

        return False, None

    def recover_validation_blockers(self) -> int:
        recovered = 0
        if hasattr(self, "fill_easy_apply_required_fields"):
            self.fill_easy_apply_required_fields()
        self.bot.process_questions()
        for method_name in (
            "recover_inline_validation_errors", "recover_unanswered_radio_groups",
            "recover_empty_required_text_fields", "recover_required_checkboxes",
            "recover_unselected_comboboxes",
        ):
            fn = getattr(self, method_name, None)
            if callable(fn):
                recovered += fn()
        return recovered

    def get_easy_apply_progress(self) -> int | None:
        try:
            progress = self.bot.browser.find_element(By.CSS_SELECTOR, "progress.artdeco-completeness-meter-linear__progress-element")
            val = progress.get_attribute("value")
            if val is not None and str(val).isdigit():
                return int(val)
        except Exception:
            pass
        try:
            region = self.bot.browser.find_element(By.CSS_SELECTOR, "div[role='region'][aria-label*='progress']")
            match = re.search(r"(\d+)\s*percent", (region.get_attribute("aria-label") or "").lower())
            if match:
                return int(match.group(1))
        except Exception:
            pass
        return None

    def wait_for_progress_change(self, previous_progress: int | None, timeout_seconds: float = 8.0) -> int | None:
        end = time.time() + timeout_seconds
        while time.time() < end:
            current = self.get_easy_apply_progress()
            if (previous_progress is None and current is not None) or (current is not None and current != previous_progress):
                return current
            page_text = (self.bot.browser.page_source or "").lower()
            if "application was sent" in page_text or "application submitted" in page_text:
                return current
            time.sleep(POLL_INTERVAL_SECONDS)
        return self.get_easy_apply_progress()

    def is_already_applied_job_page(self) -> bool:
        try:
            if any(self.bot.is_present(loc) for loc in (
                (By.CSS_SELECTOR, "span.artdeco-inline-feedback__message"),
                (By.CSS_SELECTOR, ".jobs-s-apply__applied-date"),
                (By.CSS_SELECTOR, "div.jobs-applied-banner"),
            )):
                return True
            for span in self.bot.browser.find_elements(By.CSS_SELECTOR, "span, p, div"):
                t = (span.text or "").strip().lower()
                if t.startswith("applied ") or t.startswith("applied on ") or t == "applied":
                    return True
        except Exception:
            pass
        return False

    def _is_sdui_apply_page(self) -> bool:
        try:
            url = (self.bot.browser.current_url or "").lower()
            return ("/apply/" in url or "opensduiapplyflow=true" in url) and ("linkedin.com" in url or "example.com" in url)
        except Exception:
            return False

    def find_easy_apply_modal(self):
        if len(self.bot.browser.window_handles) > 1:
            try:
                self.bot.browser.switch_to.window(self.bot.browser.window_handles[-1])
            except Exception:
                pass

        explicit_modal_selectors = [
            "div.jobs-easy-apply-modal",
            "div[data-test-modal]",
            "div.artdeco-modal",
            "div[role='dialog'][aria-labelledby*='easy-apply']",
            "div[role='dialog'][aria-label*='Easy Apply']",
            "div[role='dialog'][aria-label*='Apply']",
            "div[data-sdui-screen*='apply']",
            "div[data-sdui-screen*='EasyApply']",
            "div[data-sdui-screen]",
            "section[aria-label*='Easy Apply']",
            "section[aria-label*='Apply']",
            "div.jobs-easy-apply-content",
            "form.jobs-easy-apply-form-section",
            "form[data-test-easy-apply-form]",
            "div[data-test-modal-container]",
            "div[data-live-test-easy-apply-modal]",
            "div[data-sdui-dialog]",
        ]
        for sel in explicit_modal_selectors:
            try:
                for modal in self.bot.browser.find_elements(By.CSS_SELECTOR, sel):
                    if modal.is_displayed():
                        sdui_screen = ""
                        try:
                            sdui_screen = str(modal.get_attribute("data-sdui-screen") or "")
                        except Exception:
                            pass
                        if "jobdetails" in sdui_screen.lower():
                            continue
                        return modal
            except Exception:
                continue

        try:
            for modal in self.bot.browser.find_elements(By.CSS_SELECTOR, "div[role='dialog']"):
                if modal.is_displayed():
                    html = (modal.get_attribute("innerHTML") or "").lower()
                    if any(k in html for k in (
                        "jobs-easy-apply", "easy apply", "submit application",
                        "review your application", "continue to next step",
                    )):
                        return modal
        except Exception:
            pass

        if self._is_sdui_apply_page():
            for fallback_sel in ("div.jobs-sdui-apply-flow", "main#main", "main", "div.job-view-layout"):
                try:
                    for el in self.bot.browser.find_elements(By.CSS_SELECTOR, fallback_sel):
                        if el.is_displayed():
                            return el
                except Exception:
                    continue
        return None

    _ACTION_SELECTORS: dict[str, list[tuple[str, str]]] = {
        "submit": [
            (By.CSS_SELECTOR, "button[data-live-test-easy-apply-submit-button]"),
            (By.CSS_SELECTOR, "button[aria-label*='Submit application']"),
            (By.CSS_SELECTOR, "button[aria-label*='Submit']"),
            (By.XPATH, "//button[contains(@aria-label, 'Submit application') or contains(@aria-label, 'Submit')]"),
            (By.XPATH, "//button[.//span[contains(normalize-space(), 'Submit application') or normalize-space()='Submit']]"),
            (By.CSS_SELECTOR, "button[data-control-name='submit_unify']"),
            (By.XPATH, "//button[contains(normalize-space(.), 'Submit application') or normalize-space(.)='Submit']"),
        ],
        "review": [
            (By.CSS_SELECTOR, "button[data-live-test-easy-apply-review-button]"),
            (By.CSS_SELECTOR, "button[aria-label*='Review your application']"),
            (By.CSS_SELECTOR, "button[aria-label*='Review']"),
            (By.XPATH, "//button[contains(@aria-label, 'Review your application') or contains(@aria-label, 'Review')]"),
            (By.XPATH, "//button[.//span[contains(normalize-space(), 'Review your application') or normalize-space()='Review']]"),
            (By.CSS_SELECTOR, "button[data-control-name='review_unify']"),
            (By.XPATH, "//button[contains(normalize-space(.), 'Review your application') or normalize-space(.)='Review']"),
        ],
        "next": [
            (By.CSS_SELECTOR, "button[data-live-test-easy-apply-next-button]"),
            (By.CSS_SELECTOR, "button[data-easy-apply-next-button]"),
            (By.CSS_SELECTOR, "button[aria-label*='Continue to next step']:not(.artdeco-pagination__button--next)"),
            (By.CSS_SELECTOR, "button[aria-label*='Next step']:not(.artdeco-pagination__button--next)"),
            (By.CSS_SELECTOR, "button[aria-label*='Continue']:not(.artdeco-pagination__button--next)"),
            (By.CSS_SELECTOR, "button[aria-label*='Next']:not(.artdeco-pagination__button--next)"),
            (By.XPATH, "//button[not(contains(@class, 'artdeco-pagination')) and (contains(@aria-label, 'Continue to next step') or contains(@aria-label, 'Next'))]"),
            (By.XPATH, "//button[not(contains(@class, 'artdeco-pagination')) and .//span[contains(normalize-space(), 'Continue to next step') or normalize-space()='Next' or contains(normalize-space(), 'Next')]]"),
            (By.CSS_SELECTOR, "button[data-control-name='continue_unify']"),
            (By.XPATH, "//button[not(contains(@class, 'artdeco-pagination')) and (contains(normalize-space(.), 'Next') or contains(normalize-space(.), 'Continue'))]"),
            (By.CSS_SELECTOR, "a[href*='/apply/'][href*='openSDUIApplyFlow']"),
            (By.XPATH, "//a[contains(normalize-space(.), 'Continue applying') or contains(normalize-space(.), 'Continue')]"),
            (By.XPATH, "//button[contains(normalize-space(.), 'Continue applying')]"),
        ],
    }

    def _get_action_selectors(self, action_name: str) -> list[tuple[str, str]]:
        res: list[tuple[str, str]] = []
        loc = getattr(self.bot, "locator", None)
        if isinstance(loc, dict) and action_name in loc and isinstance(loc[action_name], tuple):
            res.append(loc[action_name])
        for item in self._ACTION_SELECTORS.get(action_name, []):
            if item not in res:
                res.append(item)
        return res

    def _find_action_button(self, action_name: str, container: Any = None):
        selectors = self._get_action_selectors(action_name)
        try:
            btn = self.bot._find_clickable(selectors, root=container)
            if btn is not None:
                return btn
        except Exception:
            pass
        return self.bot._find_clickable(selectors)

    def has_apply_controls(self) -> bool:
        if len(self.bot.browser.window_handles) > 1:
            try:
                self.bot.browser.switch_to.window(self.bot.browser.window_handles[-1])
            except Exception:
                pass

        modal = self.find_easy_apply_modal()
        if modal is not None:
            return True

        if self._is_sdui_apply_page():
            try:
                inputs = self.bot.browser.find_elements(By.CSS_SELECTOR, "input:not([type='hidden']), select, textarea, button.artdeco-button--primary, form")
                if any(e.is_displayed() for e in inputs):
                    return True
            except Exception:
                pass
            for action in ("submit", "review", "next"):
                if self._find_action_button(action) is not None:
                    return True

        current_url = (getattr(self.bot.browser, "current_url", "") or "").lower()
        if "/apply/" in current_url and "linkedin.com/jobs" in current_url:
            return True

        if not ("currentjobid" in current_url or "/search" in current_url):
            structural_selectors = [
                (By.CSS_SELECTOR, "progress.artdeco-completeness-meter-linear__progress-element"),
                (By.CSS_SELECTOR, "div[role='region'][aria-label*='progress']"),
                (By.CSS_SELECTOR, "div.jobs-easy-apply-form-section__grouping"),
                (By.CSS_SELECTOR, "form.jobs-easy-apply-form-section"),
            ]
            for by, value in structural_selectors:
                try:
                    if any(e.is_displayed() for e in self.bot.browser.find_elements(by, value)):
                        return True
                except Exception:
                    continue

        return False

    def _is_external_redirect(self) -> bool:
        try:
            url = (self.bot.browser.current_url or "").lower()
            return any(domain in url for domain in self.EXTERNAL_ATS_DOMAINS)
        except Exception:
            return False

    def wait_for_apply_flow_ready(self, timeout_seconds: float = 8.0) -> tuple[bool, str]:
        end = time.time() + timeout_seconds
        while time.time() < end:
            if self._is_external_redirect():
                return False, "external_redirect"
            limit_reached, _ = self.detect_daily_easy_apply_limit()
            if limit_reached:
                return False, "daily_limit"
            if self._is_sdui_apply_page() and self.has_apply_controls():
                return True, "sdui_page"
            if self.find_easy_apply_modal() is not None:
                return True, "modal"
            if self.has_apply_controls():
                return True, "controls"
            time.sleep(POLL_INTERVAL_SECONDS)
        return False, "timeout"

    def retry_open_apply_flow(self) -> tuple[bool, str]:
        current_job_id = getattr(self.bot, "current_job_id", "") or ""
        if current_job_id:
            direct_url = f"https://www.linkedin.com/jobs/view/{current_job_id}/apply/"
            try:
                self.bot.browser.get(direct_url)
                ready, mode = self.wait_for_apply_flow_ready(timeout_seconds=4.0)
                if ready:
                    return True, f"retry_direct_apply_url_{mode}"
            except Exception as exc:
                log.debug(f"Direct apply URL fallback error: {exc}")

        button = self.bot.get_easy_apply_button()
        if button:
            self.bot._click_easy_apply(button)
            ready, mode = self.wait_for_apply_flow_ready(timeout_seconds=4.0)
            if ready:
                return True, f"button_reclick_{mode}"

        return False, "retry_failed"

    def is_submit_confirmation_state(self) -> bool:
        phrases = (
            "your application was sent", "your application was submitted",
            "application sent", "application submitted", "application has been sent",
            "application was received", "application received", "thanks for applying",
            "thank you for applying", "your application went to", "you applied on",
        )
        try:
            if any(p in (self.bot.browser.page_source or "").lower() for p in phrases):
                return True
        except Exception:
            pass

        modal = self.find_easy_apply_modal()
        if modal is not None:
            try:
                for attr in ("innerHTML", "outerHTML"):
                    if any(p in str(modal.get_attribute(attr) or "").lower() for p in phrases):
                        return True
                if any(p in (getattr(modal, "text", "") or "").lower() for p in phrases):
                    return True
                buttons = modal.find_elements(By.TAG_NAME, "button")
                if any((getattr(b, "text", "") or "").strip().lower() in ("done", "dismiss", "close") for b in buttons):
                    if not modal.find_elements(By.CSS_SELECTOR, "input:not([type='hidden']), select, textarea"):
                        return True
            except Exception as exc:
                log.debug(f"Error checking modal confirmation state: {exc}")
        return False

    def detect_easy_apply_state(self) -> tuple[str, dict]:
        modal = self.find_easy_apply_modal()
        is_sdui = self._is_sdui_apply_page()
        current_url = (getattr(self.bot.browser, "current_url", "") or "").lower()
        is_search_page = ("currentjobid" in current_url or "/search" in current_url)

        if modal is None and not is_sdui and is_search_page:
            details = {
                "has_modal": False,
                "has_submit": False,
                "has_review": False,
                "has_next": False,
                "is_confirmation": False,
            }
            return "outside_modal", details

        submit_btn = self._find_action_button("submit", container=modal)
        review_btn = self._find_action_button("review", container=modal)
        next_btn = self._find_action_button("next", container=modal)

        has_submit = submit_btn is not None
        if has_submit and submit_btn is not None:
            raw_text = getattr(submit_btn, "text", "")
            btn_text = raw_text if isinstance(raw_text, str) else ""
            try:
                raw_aria = submit_btn.get_attribute("aria-label")
                aria_text = raw_aria if isinstance(raw_aria, str) else ""
            except Exception:
                aria_text = ""
            s_text = f"{btn_text} {aria_text}".strip().lower()
            if s_text and any(k in s_text for k in ("next", "continue", "review")):
                has_submit = False

        details = {
            "has_modal": modal is not None,
            "has_submit": has_submit,
            "has_review": review_btn is not None,
            "has_next": next_btn is not None,
            "is_confirmation": self.is_submit_confirmation_state(),
        }

        if details["is_confirmation"]:
            return "done", details

        progress = self.get_easy_apply_progress()
        if progress is not None and progress < 80:
            if details["has_next"]:
                return "next", details
            if details["has_review"]:
                return "review", details

        if details["has_submit"]:
            return "submit", details
        if details["has_review"]:
            return "review", details
        if details["has_next"]:
            return "next", details

        return ("modal_no_cta" if details["has_modal"] else "outside_modal"), details

    def collect_apply_stall_diagnostics(self, state: str, progress: int | None, loop: int) -> dict:
        modal = self.find_easy_apply_modal()
        visible_ctas = [
            name for name in ("next", "review", "submit")
            if self._find_action_button(name, container=modal) is not None
        ]
        empty_samples = []
        try:
            fields = self.bot.browser.find_elements(By.CSS_SELECTOR, "input[required], textarea[required], select[required]")
            for f in fields:
                if f.is_displayed() and not (f.get_attribute("value") or "").strip():
                    empty_samples.append(f.get_attribute("id") or f.get_attribute("aria-label") or "required_field")
        except Exception:
            pass

        errors = []
        try:
            for n in self.bot.browser.find_elements(By.CSS_SELECTOR, ".artdeco-inline-feedback__message, .jobs-easy-apply-form-error, [role='alert']"):
                if n.is_displayed() and (n.text or "").strip():
                    errors.append(n.text.strip())
        except Exception:
            pass

        return {
            "state": state, "loop": loop, "progress": progress,
            "has_modal": modal is not None,
            "visible_ctas": visible_ctas,
            "required_empty_count": len(empty_samples),
            "required_empty_samples": empty_samples[:6],
            "validation_errors": errors[:6],
        }

    def send_resume(self) -> bool:
        submitted = False
        try:
            flow_state = self._initialize_apply_flow()
            if flow_state is None:
                return False
            loop, last_progress, last_transition_at = flow_state
            submitted = self._run_apply_step_loop(loop, last_progress, last_transition_at)
        except Exception as exc:
            log.error(f"Cannot apply to this job: {exc}")
            self.bot.log_event("easy_apply_flow_error", error=str(exc))
            self.bot._dump_failure_snapshot("easy_apply_flow_error")
        return submitted

    def _initialize_apply_flow(self) -> tuple[int, int | None, float] | None:
        loop = 0
        last_progress = self.get_easy_apply_progress()
        last_transition_at = time.time()
        self.bot.log_event("easy_apply_flow_start")
        self.bot._dump_debug_html("easy_apply_flow_start")
        flow_ready, mode = self.wait_for_apply_flow_ready(timeout_seconds=8.0)
        self.bot.log_event("easy_apply_flow_ready", ready=flow_ready, mode=mode)
        self.bot._dump_debug_html("easy_apply_flow_ready", extra={"ready": flow_ready, "mode": mode})

        if not flow_ready:
            if mode == "daily_limit":
                self.bot.request_stop("daily_easy_apply_limit_reached", job_id=self.bot.current_job_id or "")
                self.bot._dump_failure_snapshot("daily_limit_reached")
                return None
            retried_ok, retry_mode = self.retry_open_apply_flow()
            self.bot.log_event("easy_apply_flow_retry", success=retried_ok, mode=retry_mode)
            self.bot._dump_debug_html("easy_apply_flow_retry", extra={"success": retried_ok, "mode": retry_mode})
            if not retried_ok:
                reason = "daily_limit_reached" if retry_mode == "daily_limit" else "apply_flow_not_detected"
                if retry_mode == "daily_limit":
                    self.bot.request_stop("daily_easy_apply_limit_reached", job_id=self.bot.current_job_id or "")
                self.bot.log_event("easy_apply_flow_stalled", progress=None, loop=loop, reason=reason)
                self.bot._dump_failure_snapshot(reason)
                return None
            last_progress = self.get_easy_apply_progress()
            last_transition_at = time.time()
        return loop, last_progress, last_transition_at

    def _run_apply_step_loop(self, loop: int, last_progress: int | None, last_transition_at: float) -> bool:
        submitted = False
        unchanged_progress_loops = 0
        validation_recovery_attempts = 0
        submit_clicked = False
        last_state = None
        no_action_loops = 0

        while loop < 20:
            stall_seconds = time.time() - last_transition_at
            if stall_seconds > self.bot.max_apply_seconds:
                self.bot.log_event("easy_apply_flow_timeout", elapsed_seconds=round(stall_seconds, 2), max_apply_seconds=self.bot.max_apply_seconds, progress=self.get_easy_apply_progress())
                self.bot._dump_failure_snapshot("apply_flow_timeout")
                break
            loop += 1
            time.sleep(STATE_MACHINE_PAUSE_SECONDS)

            progress = self.get_easy_apply_progress()
            self.bot.log_event("easy_apply_step_enter", progress=progress, loop=loop)
            self.bot._dump_debug_html(f"step_enter_loop_{loop}", extra={"progress": progress})

            state, state_details = self.detect_easy_apply_state()
            if state != last_state:
                self.bot.log_event("easy_apply_state_change", from_state=last_state, to_state=state, loop=loop, progress=progress)
                last_transition_at = time.time()
                last_state = state
                validation_recovery_attempts = 0
            self.bot.log_event("easy_apply_state", state=state, loop=loop, progress=progress, **state_details)
            if state == "done":
                submitted = True
                self.bot.log_event("easy_apply_flow_done", status="submitted", mode="state_machine_done")
                self.bot._dump_debug_html("state_machine_done", extra={"state": state, "details": state_details})
                break

            recovered_count = self.recover_validation_blockers()
            if recovered_count:
                self.bot.log_event("validation_recovery", recovered_fields=recovered_count, progress=progress, loop=loop)
                self.bot._dump_debug_html(f"validation_recovery_loop_{loop}", extra={"progress": progress, "recovered_fields": recovered_count})

            self._try_upload_documents()
            action, selectors = self._resolve_step_action(state)

            if action is None:
                no_action_loops += 1
                modal = self.find_easy_apply_modal()
                fallback_clicked = False
                if modal is not None:
                    try:
                        for btn in modal.find_elements(By.CSS_SELECTOR, "button, a[role='button'], a[href*='/apply/']"):
                            try:
                                if not (btn.is_displayed() and btn.is_enabled()):
                                    continue
                                txt = (btn.text or "").strip().lower()
                                aria = (btn.get_attribute("aria-label") or "").strip().lower()
                                combined = f"{txt} {aria}"
                                if any(k in combined for k in ("continue", "next", "review", "submit", "apply")):
                                    if self.bot._safe_click(btn):
                                        log.info(f"Clicked fallback action button in modal: '{txt or aria}'")
                                        fallback_clicked = True
                                        time.sleep(MICRO_PAUSE_SECONDS)
                                        break
                            except Exception:
                                continue
                    except Exception as exc:
                        log.debug(f"Fallback button search in modal failed: {exc}")

                if fallback_clicked:
                    last_transition_at = time.time()
                    continue

                diagnostics = self.collect_apply_stall_diagnostics(state=state, progress=progress, loop=loop)
                self.bot.log_event("easy_apply_flow_stalled", progress=progress, loop=loop, reason="no_action_resolved", diagnostics=diagnostics)
                if no_action_loops >= 3 or stall_seconds > max(6.0, self.bot.max_apply_seconds / 2):
                    self.bot._dump_failure_snapshot("no_action_resolved")
                    break
                continue

            no_action_loops = 0

            modal = self.find_easy_apply_modal()
            button = self._find_action_button(action, container=modal)
            if button is None:
                button = self.bot._find_clickable(selectors)
            if button is None or not self.bot._safe_click(button):
                diagnostics = self.collect_apply_stall_diagnostics(state=state, progress=progress, loop=loop)
                reason = f"{action}_button_not_found" if button is None else f"{action}_click_failed"
                self.bot.log_event("easy_apply_flow_stalled", progress=progress, loop=loop, reason=reason, diagnostics=diagnostics)
                self.bot._dump_failure_snapshot(reason)
                break

            self.bot.log_event("easy_apply_click", step=action, progress_before=progress, loop=loop)
            self.bot._dump_debug_html(f"clicked_{action}_loop_{loop}", extra={"progress_before": progress})
            next_progress = self.wait_for_progress_change(progress, timeout_seconds=8.0)
            self.bot.log_event("easy_apply_step_exit", step=action, progress_before=progress, progress_after=next_progress, loop=loop)
            self.bot._dump_debug_html(f"step_exit_{action}_loop_{loop}", extra={"progress_before": progress, "progress_after": next_progress})

            if next_progress is not None and next_progress != progress:
                last_progress, last_transition_at, unchanged_progress_loops = next_progress, time.time(), 0
            elif action in ("next", "review"):
                last_transition_at = time.time()
                unchanged_progress_loops += 1
            elif progress is not None and progress != last_progress:
                last_progress, last_transition_at, unchanged_progress_loops = progress, time.time(), 0

            if unchanged_progress_loops >= 3 and action in ("next", "review"):
                should_break, validation_recovery_attempts, unchanged_progress_loops, last_transition_at = self._handle_stalled_step(
                    state, progress, loop, validation_recovery_attempts, unchanged_progress_loops, last_transition_at
                )
                if should_break:
                    break
                continue

            if action == "submit":
                submitted, submit_clicked = self._handle_submit_action(submit_clicked)
                if submitted:
                    break

        if submit_clicked and not submitted:
            self.bot.log_event("easy_apply_flow_stalled", progress=self.get_easy_apply_progress(), loop=loop, reason="submit_clicked_no_confirmation")
            self.bot._dump_failure_snapshot("submit_clicked_no_confirmation")
        return submitted

    def _handle_stalled_step(
        self, state: str, progress: int | None, loop: int, recovery_attempts: int, unchanged_loops: int, last_transition: float
    ) -> tuple[bool, int, int, float]:
        diagnostics = self.collect_apply_stall_diagnostics(state=state, progress=progress, loop=loop)
        if diagnostics.get("validation_errors") or int(diagnostics.get("required_empty_count", 0)) > 0:
            if recovery_attempts < 2:
                recovered_blockers = self.recover_validation_blockers()
                if recovered_blockers:
                    self.bot.log_event("validation_block_recovery", recovered_fields=recovered_blockers, progress=progress, loop=loop, attempt=recovery_attempts + 1, diagnostics=diagnostics)
                    return False, recovery_attempts + 1, 0, time.time()
            self.bot.log_event("easy_apply_flow_stalled", progress=progress, loop=loop, reason="validation_blocked", diagnostics=diagnostics)
            self.bot._dump_failure_snapshot("validation_blocked")
            return True, recovery_attempts, unchanged_loops, last_transition
        return False, recovery_attempts, unchanged_loops, last_transition

    def dismiss_easy_apply_modal(self) -> bool:
        try:
            dismiss_selectors = [
                (By.CSS_SELECTOR, "button[aria-label='Dismiss']"),
                (By.CSS_SELECTOR, "button[data-test-modal-close-btn]"),
                (By.CSS_SELECTOR, ".artdeco-modal__dismiss"),
                (By.XPATH, "//button[@aria-label='Dismiss']"),
            ]
            btn = self.bot._find_clickable(dismiss_selectors)
            if btn is not None:
                self.bot._safe_click(btn)
                time.sleep(MICRO_PAUSE_SECONDS)
                discard_btn = self.bot._find_clickable([
                    (By.CSS_SELECTOR, "button[data-control-name='discard_application_confirm_btn']"),
                    (By.XPATH, "//button[contains(., 'Discard')]"),
                ])
                if discard_btn is not None:
                    self.bot._safe_click(discard_btn)
                return True
        except Exception as exc:
            log.debug(f"Error dismissing modal: {exc}")
        return False

    def _handle_submit_action(self, submit_clicked: bool) -> tuple[bool, bool]:
        submit_clicked = True
        if bool(getattr(getattr(self.bot, "runtime", None), "dry_run", False)):
            log.info("[DRY RUN] Easy Apply reached submit step - simulation successful.")
            self.bot.log_event("easy_apply_dry_run_submitted", job_id=self.bot.current_job_id or "", title=self.bot.browser.title)
            self.dismiss_easy_apply_modal()
            return True, submit_clicked

        time.sleep(CLICK_PAUSE_SECONDS)
        modal_after_submit = self.find_easy_apply_modal()
        confirmation = self.is_submit_confirmation_state()
        self.bot.log_event("easy_apply_submit_check", modal_still_open=bool(modal_after_submit), confirmation_detected=confirmation)
        if confirmation or modal_after_submit is None:
            log.info("Application Submitted")
            self.bot.log_event("easy_apply_flow_done", status="submitted")
            self.bot._dump_debug_html("submit_confirmed", extra={"confirmation_detected": confirmation, "modal_closed": modal_after_submit is None})
            return True, submit_clicked
        return False, submit_clicked

    def _select_matching_resume(self) -> str | None:
        from pathlib import Path
        valid_exts = (".pdf", ".doc", ".docx")

        def _is_valid_resume_file(path_str: str | Path | None) -> bool:
            if not path_str:
                return False
            return str(path_str).lower().strip().endswith(valid_exts)

        uploads = getattr(self.bot, "uploads", {})
        if isinstance(uploads, str) and _is_valid_resume_file(uploads):
            return uploads
        if isinstance(uploads, dict) and uploads:
            title = (getattr(self.bot.browser, "title", "") or "").lower()
            for key, path in uploads.items():
                k_low = str(key).lower()
                if k_low not in ("resume", "cover letter", "cover_letter", "default") and k_low in title:
                    if _is_valid_resume_file(path):
                        return str(path)
            for default_key in ("Resume", "resume", "default", "Default"):
                if default_key in uploads and _is_valid_resume_file(uploads[default_key]):
                    return str(uploads[default_key])
            for v in uploads.values():
                if _is_valid_resume_file(v):
                    return str(v)

        # Fallback: check resumes/ directory for resume.pdf or any available PDF
        default_resume = Path("resumes/resume.pdf")
        if default_resume.exists():
            return str(default_resume)
        resumes_dir = Path("resumes")
        if resumes_dir.exists():
            for pdf_file in resumes_dir.glob("*.pdf"):
                return str(pdf_file)
        root_resume = Path("resume.pdf")
        if root_resume.exists():
            return str(root_resume)

        return None

    def _find_file_input(self, selectors: Sequence[tuple[str, str]]):
        for by, value in selectors:
            try:
                for element in self.bot.browser.find_elements(by, value):
                    return element
            except Exception:
                continue
        return None

    def _try_upload_documents(self) -> None:
        from pathlib import Path
        try:
            resume_radios = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                "input[type='radio'][id*='resume'], input[type='radio'][name*='resume'], "
                "div.jobs-document-upload__resume-card input[type='radio'], "
                "div[data-test-document-upload-resume-card] input[type='radio']"
            )
            if resume_radios:
                is_selected = any(r.is_selected() for r in resume_radios if r.is_displayed())
                if not is_selected:
                    for r in resume_radios:
                        if r.is_displayed() and r.is_enabled():
                            self.bot._safe_click(r)
                            self.bot.log_event("existing_resume_selected")
                            break
                return
        except Exception as exc:
            log.debug(f"Checking existing resume selection failed: {exc}")

        try:
            resume_path = self._select_matching_resume()
            if resume_path:
                resume_el = self._find_file_input([
                    (By.XPATH, "//*[contains(@id, 'jobs-document-upload-file-input-upload-resume')]"),
                    (By.CSS_SELECTOR, "input[type='file'][id*='upload-resume']"),
                    (By.CSS_SELECTOR, "input[type='file'][name*='file']"),
                    (By.CSS_SELECTOR, "input[type='file']"),
                ])
                if resume_el is not None:
                    full_path = str(Path(resume_path).expanduser().resolve())
                    if Path(full_path).exists():
                        resume_el.send_keys(full_path)
                        self.bot.log_event("document_uploaded", type="resume", path=resume_path)
                    else:
                        log.warning(
                            f"Resume file configured at '{resume_path}' does not exist on disk! "
                            f"Please ensure your PDF resume is placed at that path."
                        )
            else:
                uploads = getattr(self.bot, "uploads", {})
                configured = uploads.get("Resume") if isinstance(uploads, dict) else uploads
                if configured and str(configured).lower().endswith(".md"):
                    log.debug(
                        "Configured resume is a Markdown file ('resume.md'). "
                        "LinkedIn file uploads require .pdf or .doc. "
                        "Skipping file upload to use pre-uploaded LinkedIn profile resume."
                    )
        except Exception as exc:
            log.debug(f"Document upload failed: {exc}")

        try:
            cv = self.bot.uploads.get("Cover Letter") or self.bot.uploads.get("cover_letter")
            if cv and cv.lower().endswith((".pdf", ".doc", ".docx")):
                cv_el = self._find_file_input([
                    (By.XPATH, "//*[contains(@id, 'jobs-document-upload-file-input-upload-cover-letter')]"),
                    (By.CSS_SELECTOR, "input[type='file'][id*='upload-cover-letter']"),
                ])
                if cv_el is not None:
                    full_cv_path = str(Path(cv).expanduser().resolve())
                    if Path(full_cv_path).exists():
                        cv_el.send_keys(full_cv_path)
                        self.bot.log_event("document_uploaded", type="cover_letter", path=cv)
                    else:
                        log.warning(
                            f"Cover letter configured at '{cv}' does not exist on disk."
                        )
        except Exception as exc:
            log.debug(f"Cover letter upload failed: {exc}")

    def _resolve_step_action(self, state: str) -> tuple[str | None, list[tuple[str, str]]]:
        if state == "submit":
            if hasattr(self, "uncheck_follow_company"):
                self.uncheck_follow_company()
            return "submit", self._get_action_selectors("submit")
        if state == "review":
            return "review", self._get_action_selectors("review")
        if state == "next":
            return "next", self._get_action_selectors("next")
        return None, []
