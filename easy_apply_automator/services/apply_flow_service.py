from __future__ import annotations

import re
import time

from selenium.webdriver.common.by import By

from easy_apply_automator.observability.logger import log

from .base import ServiceBase


class ApplyFlowService(ServiceBase):
    def detect_daily_easy_apply_limit(self) -> tuple[bool, str | None]:
        try:
            page_source = (self.bot.browser.page_source or "").replace("’", "'").lower()
            markers = (
                "you reached today's easy apply limit",
                "you reached todays easy apply limit",
                "we limit easy apply submissions",
                "continue applying tomorrow",
                "easyapplyfuselimitdialogmodal",
                '"jobapplicationlimitreached":true',
            )
            for marker in markers:
                if marker in page_source:
                    return True, marker
        except Exception:
            pass

        try:
            dialogs = self.bot.browser.find_elements(
                By.CSS_SELECTOR, "dialog[open], [role='dialog'], div[data-test-modal]"
            )
            for dialog in dialogs:
                try:
                    if not dialog.is_displayed():
                        continue
                    dialog_text = " ".join(
                        filter(
                            None,
                            (
                                dialog.text or "",
                                dialog.get_attribute("data-sdui-screen") or "",
                                dialog.get_attribute("aria-label") or "",
                            ),
                        )
                    )
                    normalized = dialog_text.replace("’", "'").lower()
                    if "easyapplyfuselimitdialogmodal" in normalized:
                        return True, "dialog_screen"
                    if "easy apply limit" in normalized and (
                        "today" in normalized
                        or "tomorrow" in normalized
                        or "continue applying" in normalized
                    ):
                        return True, "dialog_text"
                except Exception:
                    continue
        except Exception:
            pass

        return False, None

    def recover_unanswered_radio_groups(self) -> int:
        recovered = 0
        try:
            groups = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                ".jobs-easy-apply-form-section__grouping, fieldset, .fb-form-element",
            )
        except Exception:
            return recovered

        for group in groups:
            try:
                if not group.is_displayed():
                    continue
                radios = group.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                if not radios or any(r.is_selected() for r in radios):
                    continue

                raw_question = group.text or ""
                question = self.bot._clean_question_text(raw_question)
                direct = self.bot._derive_direct_answer(question)
                answer = (
                    direct
                    if direct is not None
                    else self.bot.ans_question(question.lower())
                )

                matched_radio = None
                for radio in radios:
                    if self.bot._radio_matches_answer(group, radio, answer):
                        matched_radio = radio
                        break

                target_radio = matched_radio
                if target_radio is None:
                    for radio in radios:
                        if radio.is_displayed() and radio.is_enabled():
                            target_radio = radio
                            break
                if target_radio is None:
                    continue

                rid = target_radio.get_attribute("id") or ""
                label_clicked = False
                if rid:
                    try:
                        label_el = group.find_element(By.CSS_SELECTOR, f"label[for='{rid}']")
                        self.bot._safe_click(label_el)
                        label_clicked = True
                    except Exception:
                        pass
                if not label_clicked and not self.bot._safe_click(target_radio):
                    continue

                recovered += 1
                self.bot.log_event(
                    "question_answered",
                    kind=(
                        "required_radio_recovery"
                        if matched_radio is not None
                        else "required_radio_first_option_recovery"
                    ),
                    question=question,
                    answer=answer,
                )
            except Exception:
                continue
        return recovered

    def recover_empty_required_text_fields(self) -> int:
        recovered = 0
        try:
            fields = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                "textarea[required], textarea[aria-required='true'], "
                "input[required], input[aria-required='true']",
            )
        except Exception:
            return recovered

        for field in fields:
            try:
                if not field.is_displayed():
                    continue
                tag_name = (field.tag_name or "").lower()
                input_type = (field.get_attribute("type") or "").lower()
                if tag_name == "input" and input_type in {
                    "hidden",
                    "file",
                    "checkbox",
                    "radio",
                    "submit",
                    "button",
                    "search",
                }:
                    continue

                value = (field.get_attribute("value") or "").strip()
                if value:
                    continue

                field_id = (field.get_attribute("id") or "").strip()
                question = ""
                if field_id:
                    labels = self.bot.browser.find_elements(
                        By.CSS_SELECTOR, f"label[for='{field_id}']"
                    )
                    if labels:
                        question = self.bot._clean_question_text(labels[0].text or "")
                if not question:
                    question = self.bot._clean_question_text(
                        (field.get_attribute("aria-label") or "").strip()
                    )
                if not question:
                    continue

                direct = self.bot._derive_direct_answer(question, field_id)
                answer = (
                    direct
                    if direct is not None
                    else self.bot.ans_question(question.lower())
                )
                normalized_answer = self.bot._normalize_text_answer(
                    question, answer, field_id
                )
                normalized_answer = self.bot.questions.humanize_free_text_answer(
                    question,
                    normalized_answer,
                    "textarea" if tag_name == "textarea" else "text",
                ).strip()
                if not normalized_answer:
                    normalized_answer = "N/A"

                is_typeahead = (
                    field.get_attribute("role") == "combobox"
                    or field.get_attribute("aria-autocomplete") in ("list", "both")
                )
                if is_typeahead:
                    if not self.bot._fill_typeahead_input(field, normalized_answer):
                        continue
                else:
                    field.clear()
                    field.send_keys(normalized_answer)

                recovered += 1
                self.bot.log_event(
                    "question_answered",
                    kind=(
                        "required_textarea_recovery"
                        if tag_name == "textarea"
                        else "required_text_recovery"
                    ),
                    question=question,
                    answer=normalized_answer,
                )
            except Exception:
                continue
        return recovered

    def recover_validation_blockers(self) -> int:
        recovered = 0
        self.fill_easy_apply_required_fields()
        self.bot.process_questions()
        recovered += self.recover_inline_validation_errors()
        recovered += self.recover_unanswered_radio_groups()
        recovered += self.recover_empty_required_text_fields()
        return recovered

    def recover_inline_validation_errors(self) -> int:
        recovered = 0
        try:
            bad_inputs = self.bot.browser.find_elements(
                By.CSS_SELECTOR, "input.fb-dash-form-element__error-field"
            )
            for input_el in bad_inputs:
                try:
                    input_id = input_el.get_attribute("id") or ""
                    question = ""
                    if input_id:
                        labels = self.bot.browser.find_elements(
                            By.CSS_SELECTOR, f"label[for='{input_id}']"
                        )
                        if labels:
                            question = (labels[0].text or "").strip()
                    if not question and "numeric" not in input_id.lower():
                        continue
                    answer = self.bot._coerce_numeric_answer(question, "")
                    input_el.clear()
                    input_el.send_keys(answer)
                    recovered += 1
                except Exception:
                    continue
        except Exception:
            return recovered
        return recovered

    def get_easy_apply_progress(self) -> int | None:
        try:
            progress = self.bot.browser.find_element(
                By.CSS_SELECTOR,
                "progress.artdeco-completeness-meter-linear__progress-element",
            )
            value = progress.get_attribute("value")
            if value is not None and str(value).isdigit():
                return int(value)
        except Exception:
            pass
        try:
            region = self.bot.browser.find_element(
                By.CSS_SELECTOR, "div[role='region'][aria-label*='progress']"
            )
            aria = (region.get_attribute("aria-label") or "").lower()
            match = re.search(r"(\d+)\s*percent", aria)
            if match:
                return int(match.group(1))
        except Exception:
            pass
        return None

    def wait_for_progress_change(
        self, previous_progress: int | None, timeout_seconds: float = 8.0
    ) -> int | None:
        end = time.time() + timeout_seconds
        while time.time() < end:
            current = self.get_easy_apply_progress()
            if previous_progress is None:
                if current is not None:
                    return current
            elif current is not None and current != previous_progress:
                return current
            page_text = (self.bot.browser.page_source or "").lower()
            if (
                "application was sent" in page_text
                or "application submitted" in page_text
            ):
                return current
            time.sleep(0.05)
        return self.get_easy_apply_progress()

    def is_already_applied_job_page(self) -> bool:
        try:
            controls = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                "button.jobs-apply-button, button.jobs-apply-button--top-card, div.jobs-apply-button--top-card button",
            )
            for control in controls:
                try:
                    if not control.is_displayed():
                        continue
                    text = (
                        (control.text or "").strip()
                        + " "
                        + (control.get_attribute("aria-label") or "").strip()
                    ).lower()
                    if "easy apply" in text:
                        return False
                    if re.search(r"\byou applied on\b|\bapplied\b", text):
                        return True
                except Exception:
                    continue
        except Exception:
            pass

        try:
            applied_labels = self.bot.browser.find_elements(
                By.XPATH,
                "//*[contains(@class,'jobs-unified-top-card') or contains(@class,'job-details-jobs-unified-top-card')]"
                "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'you applied on')]",
            )
            for label in applied_labels:
                if label.is_displayed():
                    return True
        except Exception:
            pass

        return False

    def find_easy_apply_modal(self):
        try:
            modals = self.bot.browser.find_elements(
                By.CSS_SELECTOR, "div.jobs-easy-apply-modal, div[data-test-modal]"
            )
            for modal in modals:
                if modal.is_displayed():
                    return modal
        except Exception:
            return None
        return None

    def has_apply_controls(self) -> bool:
        selectors = [
            (By.CSS_SELECTOR, "button[data-live-test-easy-apply-next-button]"),
            (By.CSS_SELECTOR, "button[data-easy-apply-next-button]"),
            (By.CSS_SELECTOR, "button[data-live-test-easy-apply-review-button]"),
            (By.CSS_SELECTOR, "button[data-live-test-easy-apply-submit-button]"),
            (By.CSS_SELECTOR, "button[aria-label*='Continue to next step']"),
            (By.CSS_SELECTOR, "button[aria-label*='Review your application']"),
            (By.CSS_SELECTOR, "button[aria-label*='Submit application']"),
            (
                By.CSS_SELECTOR,
                "progress.artdeco-completeness-meter-linear__progress-element",
            ),
        ]
        for by, value in selectors:
            try:
                if self.bot.browser.find_elements(by, value):
                    return True
            except Exception:
                continue
        current_url = (self.bot.browser.current_url or "").lower()
        return "/apply/" in current_url and "linkedin.com/jobs" in current_url

    def wait_for_apply_flow_ready(
        self, timeout_seconds: float = 8.0
    ) -> tuple[bool, str]:
        end = time.time() + timeout_seconds
        while time.time() < end:
            limit_reached, _ = self.detect_daily_easy_apply_limit()
            if limit_reached:
                return False, "daily_limit"
            if self.find_easy_apply_modal() is not None:
                return True, "modal"
            if self.has_apply_controls():
                return True, "controls"
            time.sleep(0.05)
        limit_reached, _ = self.detect_daily_easy_apply_limit()
        if limit_reached:
            return False, "daily_limit"
        if self.find_easy_apply_modal() is not None:
            return True, "modal"
        if self.has_apply_controls():
            return True, "controls"
        return False, "none"

    def retry_open_apply_flow(self) -> tuple[bool, str]:
        current_url = self.bot.browser.current_url or ""
        job_id = self.bot.current_job_id
        if "/jobs/collections/" in current_url and job_id:
            self.bot.browser.get(f"https://www.linkedin.com/jobs/view/{job_id}")
            time.sleep(0.1)
            ok, mode = self.wait_for_apply_flow_ready(timeout_seconds=6.0)
            if ok:
                return True, f"retry_collection_redirect_{mode}"

        try:
            btn = self.bot.get_easy_apply_button()
            if btn is not False:
                self.bot._click_easy_apply(btn)
                time.sleep(0.1)
                ok, mode = self.wait_for_apply_flow_ready(timeout_seconds=6.0)
                if ok:
                    return True, f"retry_click_{mode}"
        except Exception:
            pass

        try:
            apply_links = self.bot.browser.find_elements(
                By.CSS_SELECTOR, "a[href*='/jobs/view/'][href*='/apply/']"
            )
            for link in apply_links:
                href = link.get_attribute("href")
                if href:
                    self.bot.browser.get(href)
                    time.sleep(0.1)
                    ok, mode = self.wait_for_apply_flow_ready(timeout_seconds=6.0)
                    if ok:
                        return True, f"retry_href_{mode}"
        except Exception:
            pass

        return False, "retry_failed"

    def is_submit_confirmation_state(self) -> bool:
        try:
            page_text = (self.bot.browser.page_source or "").lower()
            markers = (
                "application submitted",
                "application was sent",
                "your application was sent",
                "submitted application",
            )
            return any(marker in page_text for marker in markers)
        except Exception:
            return False

    def detect_easy_apply_state(self) -> tuple[str, dict]:
        details = {
            "has_modal": self.find_easy_apply_modal() is not None,
            "has_controls": self.has_apply_controls(),
            "confirmation_detected": self.is_submit_confirmation_state(),
        }
        if details["confirmation_detected"]:
            return "done", details
        if (
            self.bot._find_clickable(
                [
                    (
                        By.CSS_SELECTOR,
                        "button[data-live-test-easy-apply-submit-button]",
                    ),
                    (By.CSS_SELECTOR, "button[aria-label*='Submit application']"),
                ]
            )
            is not None
        ):
            return "submit", details
        if (
            self.bot._find_clickable(
                [
                    (
                        By.CSS_SELECTOR,
                        "button[data-live-test-easy-apply-review-button]",
                    ),
                    (By.CSS_SELECTOR, "button[aria-label*='Review your application']"),
                ]
            )
            is not None
        ):
            return "review", details
        if (
            self.bot._find_clickable(
                [
                    (By.CSS_SELECTOR, "button[data-live-test-easy-apply-next-button]"),
                    (By.CSS_SELECTOR, "button[data-easy-apply-next-button]"),
                    (By.CSS_SELECTOR, "button[aria-label*='Continue to next step']"),
                ]
            )
            is not None
        ):
            return "next", details
        if details["has_modal"]:
            return "modal_no_cta", details
        return "outside_modal", details

    def collect_apply_stall_diagnostics(
        self, state: str, progress: int | None, loop: int
    ) -> dict:
        diagnostics = {
            "state": state,
            "loop": loop,
            "progress": progress,
            "has_modal": self.find_easy_apply_modal() is not None,
            "visible_ctas": [],
            "required_empty_count": 0,
            "required_empty_samples": [],
            "validation_errors": [],
        }

        ctas = [
            (
                "next",
                "button[data-live-test-easy-apply-next-button], button[data-easy-apply-next-button], button[aria-label*='Continue to next step']",
            ),
            (
                "review",
                "button[data-live-test-easy-apply-review-button], button[aria-label*='Review your application']",
            ),
            (
                "submit",
                "button[data-live-test-easy-apply-submit-button], button[aria-label*='Submit application']",
            ),
        ]
        for name, selector in ctas:
            try:
                elements = self.bot.browser.find_elements(By.CSS_SELECTOR, selector)
                if any(el.is_displayed() for el in elements):
                    diagnostics["visible_ctas"].append(name)
            except Exception:
                continue

        try:
            required_fields = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                "input[required], textarea[required], select[required], input[aria-required='true'], textarea[aria-required='true'], select[aria-required='true']",
            )
            empty_samples = []
            for field in required_fields:
                try:
                    if not field.is_displayed():
                        continue
                    value = (field.get_attribute("value") or "").strip()
                    if value:
                        continue
                    field_id = (field.get_attribute("id") or "").strip()
                    label_text = ""
                    if field_id:
                        labels = self.bot.browser.find_elements(
                            By.CSS_SELECTOR, f"label[for='{field_id}']"
                        )
                        if labels:
                            label_text = (labels[0].text or "").strip()
                    if not label_text:
                        label_text = (
                            (field.get_attribute("aria-label") or "").strip()
                            or field_id
                            or "unknown"
                        )
                    empty_samples.append(label_text)
                except Exception:
                    continue
            diagnostics["required_empty_count"] = len(empty_samples)
            diagnostics["required_empty_samples"] = empty_samples[:6]
        except Exception:
            pass

        try:
            errors = []
            error_nodes = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                ".artdeco-inline-feedback__message, .jobs-easy-apply-form-error, [role='alert']",
            )
            for node in error_nodes:
                try:
                    if not node.is_displayed():
                        continue
                    text = (node.text or "").strip()
                    if text:
                        errors.append(text)
                except Exception:
                    continue
            diagnostics["validation_errors"] = errors[:6]
        except Exception:
            pass

        return diagnostics

    def fill_easy_apply_required_fields(self) -> None:
        self.fill_required_radios_from_context()

        try:
            selects = self.bot.browser.find_elements(
                By.CSS_SELECTOR, "select[required], select[aria-required='true']"
            )
            for select_el in selects:
                try:
                    select_id = select_el.get_attribute("id") or ""
                    label_text = ""
                    if select_id:
                        labels = self.bot.browser.find_elements(
                            By.CSS_SELECTOR, f"label[for='{select_id}']"
                        )
                        if labels:
                            label_text = (labels[0].text or "").strip().lower()

                    current = (select_el.get_attribute("value") or "").strip().lower()
                    if current in ("", "select an option"):
                        if "phone country code" in label_text:
                            if not self.bot._select_option_by_answer(
                                select_el, "Czechia (+420)"
                            ):
                                self.bot._select_non_default_option(select_el)
                        else:
                            self.bot._select_non_default_option(select_el)
                except Exception:
                    continue
        except Exception:
            pass

    def fill_required_radios_from_context(self) -> None:
        try:
            groups = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                ".jobs-easy-apply-form-section__grouping, fieldset, .fb-form-element",
            )
        except Exception:
            return

        for group in groups:
            try:
                radios = group.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                if not radios:
                    continue
                if any(r.is_selected() for r in radios):
                    continue

                raw_question = group.text or ""
                question = self.bot._clean_question_text(raw_question)
                if not question:
                    continue

                direct = self.bot._derive_direct_answer(question)
                answer = (
                    direct
                    if direct is not None
                    else self.bot.ans_question(question.lower())
                )
                answer_aliases = self.bot._answer_aliases(answer)

                selected = False
                for radio in radios:
                    try:
                        if self.bot._radio_matches_answer(group, radio, answer):
                            rid = radio.get_attribute("id") or ""
                            label_clicked = False
                            if rid:
                                try:
                                    label_el = group.find_element(By.CSS_SELECTOR, f"label[for='{rid}']")
                                    self.bot._safe_click(label_el)
                                    label_clicked = True
                                except Exception:
                                    pass
                            if not label_clicked:
                                self.bot._safe_click(radio)
                            selected = True
                            self.bot.log_event(
                                "question_answered",
                                kind="required_radio_recovery",
                                question=question,
                                answer=answer,
                            )
                            break

                        value = (radio.get_attribute("value") or "").strip().lower()
                        if value and value in answer_aliases:
                            rid = radio.get_attribute("id") or ""
                            label_clicked = False
                            if rid:
                                try:
                                    label_el = group.find_element(By.CSS_SELECTOR, f"label[for='{rid}']")
                                    self.bot._safe_click(label_el)
                                    label_clicked = True
                                except Exception:
                                    pass
                            if not label_clicked:
                                self.bot._safe_click(radio)
                            selected = True
                            self.bot.log_event(
                                "question_answered",
                                kind="required_radio_value_recovery",
                                question=question,
                                answer=answer,
                            )
                            break
                    except Exception:
                        continue

                if not selected and {"yes", "true", "1", "y"} & answer_aliases:
                    for radio in radios:
                        if (radio.get_attribute("value") or "").strip().lower() in {
                            "true",
                            "yes",
                            "1",
                        }:
                            rid = radio.get_attribute("id") or ""
                            label_clicked = False
                            if rid:
                                try:
                                    label_el = group.find_element(By.CSS_SELECTOR, f"label[for='{rid}']")
                                    self.bot._safe_click(label_el)
                                    label_clicked = True
                                except Exception:
                                    pass
                            if not label_clicked:
                                self.bot._safe_click(radio)
                            selected = True
                            self.bot.log_event(
                                "question_answered",
                                kind="required_radio_yes_fallback",
                                question=question,
                                answer=answer,
                            )
                            break

                if not selected and {"no", "false", "0", "n"} & answer_aliases:
                    for radio in radios:
                        if (radio.get_attribute("value") or "").strip().lower() in {
                            "false",
                            "no",
                            "0",
                        }:
                            rid = radio.get_attribute("id") or ""
                            label_clicked = False
                            if rid:
                                try:
                                    label_el = group.find_element(By.CSS_SELECTOR, f"label[for='{rid}']")
                                    self.bot._safe_click(label_el)
                                    label_clicked = True
                                except Exception:
                                    pass
                            if not label_clicked:
                                self.bot._safe_click(radio)
                            selected = True
                            self.bot.log_event(
                                "question_answered",
                                kind="required_radio_no_fallback",
                                question=question,
                                answer=answer,
                            )
                            break
            except Exception:
                continue

        try:
            phone_inputs = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                "input[id*='phoneNumber-nationalNumber'], input[aria-label*='Mobile phone number']",
            )
            for phone_input in phone_inputs:
                current = (phone_input.get_attribute("value") or "").strip()
                if not current and self.bot.phone_number:
                    digits_only = re.sub(r"[^\d]", "", str(self.bot.phone_number))
                    if digits_only:
                        phone_input.send_keys(digits_only)
        except Exception:
            pass

        try:
            text_inputs = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                "input[required][type='text'], input[required][type='number'], input[aria-required='true'][type='text'], input[aria-required='true'][type='number']",
            )
            for input_el in text_inputs:
                value = (input_el.get_attribute("value") or "").strip()
                if value:
                    continue
                question = ""
                try:
                    input_id = input_el.get_attribute("id")
                    if input_id:
                        labels = self.bot.browser.find_elements(
                            By.CSS_SELECTOR, f"label[for='{input_id}']"
                        )
                        if labels:
                            question = labels[0].text.strip()
                except Exception:
                    question = ""
                if question:
                    direct = self.bot._derive_direct_answer(
                        question, input_el.get_attribute("id") or ""
                    )
                    answer = (
                        direct
                        if direct is not None
                        else self.bot.ans_question(question.lower())
                    )
                    normalized_answer = self.bot._normalize_text_answer(
                        question, answer, input_el.get_attribute("id") or ""
                    )
                    if normalized_answer:
                        is_typeahead = input_el.get_attribute("role") == "combobox" or input_el.get_attribute("aria-autocomplete") in ("list", "both")
                        if is_typeahead:
                            self.bot._fill_typeahead_input(input_el, normalized_answer)
                        else:
                            input_el.send_keys(normalized_answer)
        except Exception:
            pass

    def uncheck_follow_company(self) -> None:
        try:
            checkbox = self.bot.browser.find_element(By.ID, "follow-company-checkbox")
            if checkbox.is_selected():
                label = self.bot.browser.find_element(
                    By.CSS_SELECTOR, "label[for='follow-company-checkbox']"
                )
                self.bot._safe_click(label)
        except Exception:
            pass

    def send_resume(self) -> bool:
        submitted = False
        try:
            loop = 0
            last_progress = self.get_easy_apply_progress()
            last_transition_at = time.time()
            unchanged_progress_loops = 0
            validation_recovery_attempts = 0
            self.bot.log_event("easy_apply_flow_start")
            self.bot._dump_debug_html("easy_apply_flow_start")
            flow_ready, mode = self.wait_for_apply_flow_ready(timeout_seconds=8.0)
            self.bot.log_event("easy_apply_flow_ready", ready=flow_ready, mode=mode)
            self.bot._dump_debug_html(
                "easy_apply_flow_ready", extra={"ready": flow_ready, "mode": mode}
            )
            if not flow_ready:
                if mode == "daily_limit":
                    self.bot.request_stop(
                        "daily_easy_apply_limit_reached",
                        job_id=str(self.bot.current_job_id or ""),
                    )
                    self.bot.log_event(
                        "easy_apply_flow_blocked",
                        reason="daily_limit_reached",
                        mode=mode,
                    )
                    self.bot._dump_failure_snapshot("daily_limit_reached")
                    return False
                retried_ok, retry_mode = self.retry_open_apply_flow()
                self.bot.log_event(
                    "easy_apply_flow_retry", success=retried_ok, mode=retry_mode
                )
                self.bot._dump_debug_html(
                    "easy_apply_flow_retry",
                    extra={"success": retried_ok, "mode": retry_mode},
                )
                if not retried_ok and retry_mode == "daily_limit":
                    self.bot.request_stop(
                        "daily_easy_apply_limit_reached",
                        job_id=str(self.bot.current_job_id or ""),
                    )
                    self.bot.log_event(
                        "easy_apply_flow_blocked",
                        reason="daily_limit_reached",
                        mode=retry_mode,
                    )
                    self.bot._dump_failure_snapshot("daily_limit_reached")
                    return False
                if not retried_ok:
                    self.bot.log_event(
                        "easy_apply_flow_stalled",
                        progress=None,
                        loop=loop,
                        reason="apply_flow_not_detected",
                    )
                    self.bot._dump_failure_snapshot("apply_flow_not_detected")
                    return False
                last_progress = self.get_easy_apply_progress()
                last_transition_at = time.time()

            submit_clicked = False
            last_state = None
            while loop < 20:
                stall_seconds = time.time() - last_transition_at
                if stall_seconds > self.bot.max_apply_seconds:
                    self.bot.log_event(
                        "easy_apply_flow_timeout",
                        elapsed_seconds=round(stall_seconds, 2),
                        max_apply_seconds=self.bot.max_apply_seconds,
                        progress=self.get_easy_apply_progress(),
                    )
                    self.bot._dump_failure_snapshot("apply_flow_timeout")
                    break
                loop += 1
                time.sleep(0.15)

                progress = self.get_easy_apply_progress()
                self.bot.log_event(
                    "easy_apply_step_enter", progress=progress, loop=loop
                )
                self.bot._dump_debug_html(
                    f"step_enter_loop_{loop}", extra={"progress": progress}
                )

                state, state_details = self.detect_easy_apply_state()
                if state != last_state:
                    self.bot.log_event(
                        "easy_apply_state_change",
                        from_state=last_state,
                        to_state=state,
                        loop=loop,
                        progress=progress,
                    )
                    last_transition_at = time.time()
                    last_state = state
                    validation_recovery_attempts = 0
                self.bot.log_event(
                    "easy_apply_state",
                    state=state,
                    loop=loop,
                    progress=progress,
                    **state_details,
                )
                if state == "done":
                    submitted = True
                    self.bot.log_event(
                        "easy_apply_flow_done",
                        status="submitted",
                        mode="state_machine_done",
                    )
                    self.bot._dump_debug_html(
                        "state_machine_done",
                        extra={"state": state, "details": state_details},
                    )
                    break

                recovered_count = self.recover_validation_blockers()
                if recovered_count:
                    self.bot.log_event(
                        "validation_recovery",
                        recovered_fields=recovered_count,
                        progress=progress,
                        loop=loop,
                    )
                    self.bot._dump_debug_html(
                        f"validation_recovery_loop_{loop}",
                        extra={
                            "progress": progress,
                            "recovered_fields": recovered_count,
                        },
                    )

                try:
                    resume_locator = self.bot._find_clickable(
                        [
                            (
                                By.XPATH,
                                "//*[contains(@id, 'jobs-document-upload-file-input-upload-resume')]",
                            ),
                            (
                                By.CSS_SELECTOR,
                                "input[type='file'][id*='upload-resume']",
                            ),
                        ]
                    )
                    resume = self.bot.uploads.get("Resume")
                    if resume_locator is not None and resume:
                        resume_locator.send_keys(resume)
                except Exception:
                    pass
                try:
                    cv_locator = self.bot._find_clickable(
                        [
                            (
                                By.XPATH,
                                "//*[contains(@id, 'jobs-document-upload-file-input-upload-cover-letter')]",
                            ),
                            (
                                By.CSS_SELECTOR,
                                "input[type='file'][id*='upload-cover-letter']",
                            ),
                        ]
                    )
                    cv = self.bot.uploads.get("Cover Letter")
                    if cv_locator is not None and cv:
                        cv_locator.send_keys(cv)
                except Exception:
                    pass

                action = None
                selectors: list[tuple[str, str]] = []
                if state == "submit":
                    action = "submit"
                    self.uncheck_follow_company()
                    selectors = [
                        (
                            By.CSS_SELECTOR,
                            "button[data-live-test-easy-apply-submit-button]",
                        ),
                        (By.CSS_SELECTOR, "button[aria-label*='Submit application']"),
                    ]
                elif state == "review":
                    action = "review"
                    selectors = [
                        (
                            By.CSS_SELECTOR,
                            "button[data-live-test-easy-apply-review-button]",
                        ),
                        (
                            By.CSS_SELECTOR,
                            "button[aria-label*='Review your application']",
                        ),
                    ]
                elif state == "next":
                    action = "next"
                    selectors = [
                        (
                            By.CSS_SELECTOR,
                            "button[data-live-test-easy-apply-next-button]",
                        ),
                        (By.CSS_SELECTOR, "button[data-easy-apply-next-button]"),
                        (
                            By.CSS_SELECTOR,
                            "button[aria-label*='Continue to next step']",
                        ),
                    ]

                if action is None:
                    diagnostics = self.collect_apply_stall_diagnostics(
                        state=state, progress=progress, loop=loop
                    )
                    self.bot.log_event(
                        "easy_apply_flow_stalled",
                        progress=progress,
                        loop=loop,
                        reason="no_action_resolved",
                        diagnostics=diagnostics,
                    )
                    self.bot._dump_debug_html(
                        f"stall_no_action_loop_{loop}",
                        extra={"diagnostics": diagnostics},
                    )
                    if stall_seconds > max(6.0, self.bot.max_apply_seconds / 2):
                        self.bot._dump_failure_snapshot("no_action_resolved")
                        break
                    continue

                button = self.bot._find_clickable(selectors)
                if button is None:
                    diagnostics = self.collect_apply_stall_diagnostics(
                        state=state, progress=progress, loop=loop
                    )
                    self.bot.log_event(
                        "easy_apply_flow_stalled",
                        progress=progress,
                        loop=loop,
                        reason=f"{action}_button_not_found",
                        diagnostics=diagnostics,
                    )
                    self.bot._dump_failure_snapshot(f"{action}_button_not_found")
                    break

                if not self.bot._safe_click(button):
                    diagnostics = self.collect_apply_stall_diagnostics(
                        state=state, progress=progress, loop=loop
                    )
                    self.bot.log_event(
                        "easy_apply_flow_stalled",
                        progress=progress,
                        loop=loop,
                        reason=f"{action}_click_failed",
                        diagnostics=diagnostics,
                    )
                    self.bot._dump_failure_snapshot(f"{action}_click_failed")
                    break

                self.bot.log_event(
                    "easy_apply_click", step=action, progress_before=progress, loop=loop
                )
                self.bot._dump_debug_html(
                    f"clicked_{action}_loop_{loop}", extra={"progress_before": progress}
                )
                next_progress = self.wait_for_progress_change(
                    progress, timeout_seconds=8.0
                )
                self.bot.log_event(
                    "easy_apply_step_exit",
                    step=action,
                    progress_before=progress,
                    progress_after=next_progress,
                    loop=loop,
                )
                self.bot._dump_debug_html(
                    f"step_exit_{action}_loop_{loop}",
                    extra={
                        "progress_before": progress,
                        "progress_after": next_progress,
                    },
                )
                if next_progress is not None and next_progress != progress:
                    last_progress = next_progress
                    last_transition_at = time.time()
                    unchanged_progress_loops = 0
                elif action in ("next", "review"):
                    last_transition_at = time.time()
                    unchanged_progress_loops += 1
                elif progress is not None and progress != last_progress:
                    last_progress = progress
                    last_transition_at = time.time()
                    unchanged_progress_loops = 0

                if unchanged_progress_loops >= 3 and action in ("next", "review"):
                    diagnostics = self.collect_apply_stall_diagnostics(
                        state=state, progress=progress, loop=loop
                    )
                    if (
                        diagnostics.get("validation_errors")
                        or int(diagnostics.get("required_empty_count", 0)) > 0
                    ):
                        if validation_recovery_attempts < 2:
                            recovered_blockers = self.recover_validation_blockers()
                            if recovered_blockers:
                                validation_recovery_attempts += 1
                                unchanged_progress_loops = 0
                                last_transition_at = time.time()
                                self.bot.log_event(
                                    "validation_block_recovery",
                                    recovered_fields=recovered_blockers,
                                    progress=progress,
                                    loop=loop,
                                    attempt=validation_recovery_attempts,
                                    diagnostics=diagnostics,
                                )
                                self.bot._dump_debug_html(
                                    f"validation_block_recovery_loop_{loop}",
                                    extra={
                                        "recovered_fields": recovered_blockers,
                                        "attempt": validation_recovery_attempts,
                                        "diagnostics": diagnostics,
                                    },
                                )
                                continue
                        self.bot.log_event(
                            "easy_apply_flow_stalled",
                            progress=progress,
                            loop=loop,
                            reason="validation_blocked",
                            diagnostics=diagnostics,
                        )
                        self.bot._dump_failure_snapshot("validation_blocked")
                        break

                if action == "submit":
                    submit_clicked = True
                    time.sleep(0.2)
                    modal_after_submit = self.find_easy_apply_modal()
                    confirmation = self.is_submit_confirmation_state()
                    self.bot.log_event(
                        "easy_apply_submit_check",
                        modal_still_open=bool(modal_after_submit),
                        confirmation_detected=confirmation,
                    )
                    if confirmation or modal_after_submit is None:
                        submitted = True
                        log.info("Application Submitted")
                        self.bot.log_event("easy_apply_flow_done", status="submitted")
                        self.bot._dump_debug_html(
                            "submit_confirmed",
                            extra={
                                "confirmation_detected": confirmation,
                                "modal_closed": modal_after_submit is None,
                            },
                        )
                        break
                    continue

                continue

            if submit_clicked and not submitted:
                self.bot.log_event(
                    "easy_apply_flow_stalled",
                    progress=self.get_easy_apply_progress(),
                    loop=loop,
                    reason="submit_clicked_no_confirmation",
                )
                self.bot._dump_failure_snapshot("submit_clicked_no_confirmation")

        except Exception as exc:
            log.error(exc)
            log.error("cannot apply to this job")
            self.bot.log_event("easy_apply_flow_error", error=str(exc))
            self.bot._dump_failure_snapshot("easy_apply_flow_error")

        return submitted
