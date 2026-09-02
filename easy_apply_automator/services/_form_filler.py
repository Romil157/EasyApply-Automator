# This is an internal module intended for mixin implementation only.
# Do not import it directly; use ApplyFlowService instead.
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from selenium.webdriver.common.by import By

from easy_apply_automator.observability.logger import log

if TYPE_CHECKING:
    from easy_apply_automator.app.orchestrator import LinkedInEasyApplyOrchestrator


COUNTRY_DIAL_CODES: dict[str, list[str]] = {
    "IN": ["India (+91)", "+91", "India"],
    "US": ["United States (+1)", "+1", "United States"],
    "GB": ["United Kingdom (+44)", "+44", "United Kingdom"],
    "CA": ["Canada (+1)", "+1", "Canada"],
    "AU": ["Australia (+61)", "+61", "Australia"],
    "DE": ["Germany (+49)", "+49", "Germany"],
    "FR": ["France (+33)", "+33", "France"],
    "CZ": ["Czechia (+420)", "+420", "Czech Republic"],
    "SG": ["Singapore (+65)", "+65", "Singapore"],
    "AE": ["United Arab Emirates (+971)", "+971", "UAE"],
    "NL": ["Netherlands (+31)", "+31", "Netherlands"],
    "IE": ["Ireland (+353)", "+353", "Ireland"],
    "ES": ["Spain (+34)", "+34", "Spain"],
    "IT": ["Italy (+39)", "+39", "Italy"],
    "BR": ["Brazil (+55)", "+55", "Brazil"],
    "JP": ["Japan (+81)", "+81", "Japan"],
    "CH": ["Switzerland (+41)", "+41", "Switzerland"],
    "SE": ["Sweden (+46)", "+46", "Sweden"],
    "PL": ["Poland (+48)", "+48", "Poland"],
}


class FormFillerMixin:
    bot: LinkedInEasyApplyOrchestrator

    def _click_element_or_label(self, group, element, el_id: str) -> bool:
        """Helper to click label associated with an input or fallback to direct element click."""
        if el_id:
            try:
                label_el = group.find_element(By.CSS_SELECTOR, f"label[for='{el_id}']")
                if self.bot._safe_click(label_el):
                    return True
            except Exception:
                pass
        return bool(self.bot._safe_click(element))

    def fill_easy_apply_required_fields(self) -> None:
        self.fill_required_radios_from_context()
        self.fill_required_checkboxes_from_context()

        # Handle select elements
        try:
            selects = self.bot.browser.find_elements(
                By.CSS_SELECTOR, "select[required], select[aria-required='true'], select"
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
                    if current in ("", "select an option", "none", "0"):
                        if "phone country code" in label_text:
                            country_code = (
                                (getattr(self.bot, "location_country", "IN") or "IN")
                                .upper()
                                .strip()
                            )
                            candidates = COUNTRY_DIAL_CODES.get(country_code, [country_code])
                            selected = any(
                                self.bot._select_option_by_answer(select_el, c)
                                for c in candidates
                            )
                            if not selected:
                                self.bot._select_non_default_option(select_el)
                        else:
                            self.bot._select_non_default_option(select_el)
                except Exception as exc:
                    log.debug(f"Failed to process select element: {exc}")
        except Exception as exc:
            log.debug(f"Select element lookup failed: {exc}")

        # Handle un-prefilled national phone inputs
        try:
            phone_inputs = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                "input[id*='phoneNumber-nationalNumber'], input[aria-label*='Mobile phone number']",
            )
            for phone_input in phone_inputs:
                current = (phone_input.get_attribute("value") or "").strip()
                if not current and self.bot.phone_number:
                    digits = re.sub(r"[^\d]", "", str(self.bot.phone_number))
                    if digits:
                        phone_input.send_keys(digits)
        except Exception as exc:
            log.debug(f"Phone input logic failed: {exc}")

        # Handle initial empty required text inputs
        try:
            text_inputs = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                "input[required][type='text'], input[required][type='number'], "
                "input[aria-required='true'][type='text'], input[aria-required='true'][type='number']",
            )
            for input_el in text_inputs:
                val = (input_el.get_attribute("value") or "").strip()
                if val:
                    continue
                input_id = input_el.get_attribute("id") or ""
                question = ""
                if input_id:
                    labels = self.bot.browser.find_elements(
                        By.CSS_SELECTOR, f"label[for='{input_id}']"
                    )
                    if labels:
                        question = labels[0].text.strip()
                if question:
                    direct = self.bot._derive_direct_answer(question, input_id)
                    ans = direct if direct is not None else self.bot.ans_question(question.lower())
                    norm = self.bot._normalize_text_answer(question, ans, input_id)
                    if norm:
                        is_typeahead = input_el.get_attribute("role") == "combobox" or (
                            input_el.get_attribute("aria-autocomplete") in ("list", "both")
                        )
                        if is_typeahead:
                            self.bot._fill_typeahead_input(input_el, norm)
                        else:
                            input_el.send_keys(norm)
        except Exception as exc:
            log.debug(f"Text inputs processing failed: {exc}")

    def _process_radio_group(
        self, group, fallback_to_first: bool = False
    ) -> bool:
        """Evaluates a single radio group and clicks the best matching option."""
        try:
            radios = group.find_elements(By.CSS_SELECTOR, "input[type='radio']")
            if not radios or any(r.is_selected() for r in radios):
                return False

            raw_question = group.text or ""
            question = self.bot._clean_question_text(raw_question)
            if not question:
                return False

            direct = self.bot._derive_direct_answer(question)
            answer = direct if direct is not None else self.bot.ans_question(question.lower())
            answer_aliases = self.bot._answer_aliases(answer)

            # Strategy 1: Match by label text or value attribute
            for radio in radios:
                rid = radio.get_attribute("id") or ""
                val = (radio.get_attribute("value") or "").strip().lower()
                if self.bot._radio_matches_answer(group, radio, answer) or (val and val in answer_aliases):
                    if self._click_element_or_label(group, radio, rid):
                        self.bot.log_event(
                            "question_answered",
                            kind="required_radio_recovery",
                            question=question,
                            answer=answer,
                        )
                        return True

            # Strategy 2: Yes/True fallback
            if {"yes", "true", "1", "y"} & answer_aliases:
                for radio in radios:
                    if (radio.get_attribute("value") or "").strip().lower() in {"true", "yes", "1"}:
                        rid = radio.get_attribute("id") or ""
                        if self._click_element_or_label(group, radio, rid):
                            self.bot.log_event(
                                "question_answered",
                                kind="required_radio_yes_fallback",
                                question=question,
                                answer=answer,
                            )
                            return True

            # Strategy 3: No/False fallback
            if {"no", "false", "0", "n"} & answer_aliases:
                for radio in radios:
                    if (radio.get_attribute("value") or "").strip().lower() in {"false", "no", "0"}:
                        rid = radio.get_attribute("id") or ""
                        if self._click_element_or_label(group, radio, rid):
                            self.bot.log_event(
                                "question_answered",
                                kind="required_radio_no_fallback",
                                question=question,
                                answer=answer,
                            )
                            return True

            # Strategy 4: Fallback to first available radio option during recovery
            if fallback_to_first:
                for radio in radios:
                    if radio.is_displayed() and radio.is_enabled():
                        rid = radio.get_attribute("id") or ""
                        if self._click_element_or_label(group, radio, rid):
                            self.bot.log_event(
                                "question_answered",
                                kind="required_radio_first_option_recovery",
                                question=question,
                                answer=answer,
                            )
                            return True
        except Exception as exc:
            log.debug(f"Error evaluating radio group: {exc}")
        return False

    def fill_required_radios_from_context(self) -> None:
        try:
            groups = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                ".jobs-easy-apply-form-section__grouping, fieldset, .fb-form-element, .fb-dash-form-element, .jobs-easy-apply-form-element, div[data-test-form-element]",
            )
            for group in groups:
                self._process_radio_group(group, fallback_to_first=False)
        except Exception as exc:
            log.debug(f"Radio lookup failed in fill_required_radios_from_context: {exc}")

    def recover_unanswered_radio_groups(self) -> int:
        recovered = 0
        try:
            groups = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                ".jobs-easy-apply-form-section__grouping, fieldset, .fb-form-element, .fb-dash-form-element, .jobs-easy-apply-form-element, div[data-test-form-element]",
            )
            for group in groups:
                if group.is_displayed() and self._process_radio_group(group, fallback_to_first=True):
                    recovered += 1
        except Exception as exc:
            log.debug(f"Radio lookup failed in recover_unanswered_radio_groups: {exc}")
        return recovered

    def recover_empty_required_text_fields(self) -> int:
        recovered = 0
        try:
            fields = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                "textarea[required], textarea[aria-required='true'], "
                "input[required], input[aria-required='true']",
            )
        except Exception as exc:
            log.debug(f"Required fields lookup failed: {exc}")
            return recovered

        for field in fields:
            try:
                if not field.is_displayed():
                    continue
                tag_name = (field.tag_name or "").lower()
                input_type = (field.get_attribute("type") or "").lower()
                if tag_name == "input" and input_type in {
                    "hidden", "file", "checkbox", "radio", "submit", "button", "search"
                }:
                    continue

                if (field.get_attribute("value") or "").strip():
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
                answer = direct if direct is not None else self.bot.ans_question(question.lower())
                normalized = self.bot._normalize_text_answer(question, answer, field_id)
                normalized = self.bot.questions.humanize_free_text_answer(
                    question, normalized, "textarea" if tag_name == "textarea" else "text"
                ).strip()
                if not normalized:
                    normalized = "N/A"

                is_typeahead = field.get_attribute("role") == "combobox" or (
                    field.get_attribute("aria-autocomplete") in ("list", "both")
                )
                if is_typeahead:
                    if not self.bot._fill_typeahead_input(field, normalized):
                        continue
                else:
                    field.clear()
                    field.send_keys(normalized)

                recovered += 1
                self.bot.log_event(
                    "question_answered",
                    kind="required_textarea_recovery" if tag_name == "textarea" else "required_text_recovery",
                    question=question,
                    answer=normalized,
                )
            except Exception as exc:
                log.debug(f"Failed to recover empty text field: {exc}")
        return recovered

    def recover_inline_validation_errors(self) -> int:
        recovered = 0
        try:
            bad_inputs = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                "input.fb-dash-form-element__error-field, input[aria-invalid='true'], textarea[aria-invalid='true']",
            )
            for input_el in bad_inputs:
                try:
                    if not input_el.is_displayed():
                        continue
                    input_id = input_el.get_attribute("id") or ""
                    question = ""
                    if input_id:
                        labels = self.bot.browser.find_elements(
                            By.CSS_SELECTOR, f"label[for='{input_id}']"
                        )
                        if labels:
                            question = (labels[0].text or "").strip()
                    if not question:
                        question = (input_el.get_attribute("aria-label") or "").strip()

                    direct = self.bot._derive_direct_answer(question, input_id)
                    answer = direct if direct is not None else self.bot.ans_question(question.lower())
                    coerced = self.bot._coerce_numeric_answer(question, answer) if "numeric" in input_id.lower() or "year" in question.lower() or "experience" in question.lower() else answer
                    input_el.clear()
                    input_el.send_keys(coerced or "0")
                    recovered += 1
                except Exception as exc:
                    log.debug(f"Failed to clear error field '{input_id}': {exc}")
        except Exception as exc:
            log.debug(f"Inline validation recovery failed: {exc}")
        return recovered

    def fill_required_checkboxes_from_context(self) -> None:
        self.recover_required_checkboxes()

    def recover_required_checkboxes(self) -> int:
        recovered = 0
        try:
            checkboxes = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                "input[type='checkbox'][required], input[type='checkbox'][aria-required='true']",
            )
            for cb in checkboxes:
                try:
                    if not cb.is_displayed() or cb.is_selected():
                        continue
                    cb_id = cb.get_attribute("id") or ""
                    if "follow-company" in cb_id:
                        continue
                    if self._click_element_or_label(self.bot.browser, cb, cb_id):
                        recovered += 1
                        self.bot.log_event(
                            "question_answered", kind="required_checkbox_recovery", id=cb_id
                        )
                except Exception as exc:
                    log.debug(f"Failed to check required checkbox: {exc}")
        except Exception as exc:
            log.debug(f"Checkbox lookup failed: {exc}")
        return recovered

    def recover_unselected_comboboxes(self) -> int:
        recovered = 0
        try:
            comboboxes = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                "input[role='combobox'], div[role='combobox'], button[aria-haspopup='listbox']",
            )
            for box in comboboxes:
                try:
                    if not box.is_displayed():
                        continue
                    tag = (box.tag_name or "").lower()
                    if tag == "input" and (box.get_attribute("value") or "").strip():
                        continue
                    box_id = box.get_attribute("id") or ""
                    question = ""
                    if box_id:
                        labels = self.bot.browser.find_elements(
                            By.CSS_SELECTOR, f"label[for='{box_id}']"
                        )
                        if labels:
                            question = self.bot._clean_question_text(labels[0].text or "")
                    if not question:
                        question = self.bot._clean_question_text(
                            (box.get_attribute("aria-label") or "").strip()
                        )
                    if question:
                        direct = self.bot._derive_direct_answer(question, box_id)
                        answer = direct if direct is not None else self.bot.ans_question(question.lower())
                        normalized = self.bot._normalize_text_answer(question, answer, box_id)
                        if self.bot._fill_typeahead_input(box, normalized):
                            recovered += 1
                            self.bot.log_event(
                                "question_answered",
                                kind="combobox_recovery",
                                question=question,
                                answer=normalized,
                            )
                except Exception as exc:
                    log.debug(f"Combobox processing failed: {exc}")
        except Exception as exc:
            log.debug(f"Combobox lookup failed: {exc}")
        return recovered

    def uncheck_follow_company(self) -> None:
        try:
            checkbox = self.bot.browser.find_element(By.ID, "follow-company-checkbox")
            if checkbox.is_selected():
                label = self.bot.browser.find_element(
                    By.CSS_SELECTOR, "label[for='follow-company-checkbox']"
                )
                self.bot._safe_click(label)
        except Exception as exc:
            log.debug(f"Failed to uncheck follow company checkbox: {exc}")
