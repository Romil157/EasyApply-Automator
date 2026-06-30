# This is an internal module intended for mixin implementation only.
# Do not import it directly; use ApplyFlowService instead.
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from selenium.webdriver.common.by import By

from easy_apply_automator.observability.logger import log

if TYPE_CHECKING:
    from easy_apply_automator.app.orchestrator import LinkedInEasyApplyOrchestrator


class FormFillerMixin:
    bot: LinkedInEasyApplyOrchestrator

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
                            if not self.bot._select_option_by_answer(select_el, "Czechia (+420)"):
                                self.bot._select_non_default_option(select_el)
                        else:
                            self.bot._select_non_default_option(select_el)
                except Exception as exc:
                    log.debug(f"Failed to check/select non-default select option: {exc}")
                    continue
        except Exception as exc:
            log.debug(f"Select element lookup failed in fill_required_selects_from_context: {exc}")

    def fill_required_radios_from_context(self) -> None:
        try:
            groups = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                ".jobs-easy-apply-form-section__grouping, fieldset, .fb-form-element",
            )
        except Exception as exc:
            log.debug(f"Group lookup failed in fill_required_radios_from_context: {exc}")
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
                answer = direct if direct is not None else self.bot.ans_question(question.lower())
                answer_aliases = self.bot._answer_aliases(answer)

                selected = False
                for radio in radios:
                    try:
                        if self.bot._radio_matches_answer(group, radio, answer):
                            rid = radio.get_attribute("id") or ""
                            label_clicked = False
                            if rid:
                                try:
                                    label_el = group.find_element(
                                        By.CSS_SELECTOR, f"label[for='{rid}']"
                                    )
                                    self.bot._safe_click(label_el)
                                    label_clicked = True
                                except Exception as exc:
                                    log.debug(f"Failed to click label for rid '{rid}': {exc}")
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
                                    label_el = group.find_element(
                                        By.CSS_SELECTOR, f"label[for='{rid}']"
                                    )
                                    self.bot._safe_click(label_el)
                                    label_clicked = True
                                except Exception as exc:
                                    log.debug(f"Failed to click label for rid '{rid}': {exc}")
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
                    except Exception as exc:
                        log.debug(f"Failed to set radio option: {exc}")
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
                                    label_el = group.find_element(
                                        By.CSS_SELECTOR, f"label[for='{rid}']"
                                    )
                                    self.bot._safe_click(label_el)
                                    label_clicked = True
                                except Exception as exc:
                                    log.debug(f"Failed to click fallback label for rid '{rid}': {exc}")
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
                                    label_el = group.find_element(
                                        By.CSS_SELECTOR, f"label[for='{rid}']"
                                    )
                                    self.bot._safe_click(label_el)
                                    label_clicked = True
                                except Exception as exc:
                                    log.debug(f"Failed to click fallback label for rid '{rid}': {exc}")
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
            except Exception as exc:
                log.debug(f"Radio processing loop error for group: {exc}")
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
        except Exception as exc:
            log.debug(f"Phone number input logic failed: {exc}")

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
                except Exception as exc:
                    log.debug(f"Label lookup failed for input element '{input_id}': {exc}")
                    question = ""
                if question:
                    direct = self.bot._derive_direct_answer(
                        question, input_el.get_attribute("id") or ""
                    )
                    answer = (
                        direct if direct is not None else self.bot.ans_question(question.lower())
                    )
                    normalized_answer = self.bot._normalize_text_answer(
                        question, answer, input_el.get_attribute("id") or ""
                    )
                    if normalized_answer:
                        is_typeahead = input_el.get_attribute(
                            "role"
                        ) == "combobox" or input_el.get_attribute("aria-autocomplete") in (
                            "list",
                            "both",
                        )
                        if is_typeahead:
                            self.bot._fill_typeahead_input(input_el, normalized_answer)
                        else:
                            input_el.send_keys(normalized_answer)
        except Exception as exc:
            log.debug(f"Text inputs processing failed: {exc}")

    def recover_unanswered_radio_groups(self) -> int:
        recovered = 0
        try:
            groups = self.bot.browser.find_elements(
                By.CSS_SELECTOR,
                ".jobs-easy-apply-form-section__grouping, fieldset, .fb-form-element",
            )
        except Exception as exc:
            log.debug(f"Radio group lookup failed in recover_unanswered_radio_groups: {exc}")
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
                answer = direct if direct is not None else self.bot.ans_question(question.lower())

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
                    except Exception as exc:
                        log.debug(f"Failed to click label for rid '{rid}': {exc}")
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
            except Exception as exc:
                log.debug(f"Failed to process radio group recovery: {exc}")
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
        except Exception as exc:
            log.debug(f"Required fields lookup failed in recover_empty_required_text_fields: {exc}")
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
                answer = direct if direct is not None else self.bot.ans_question(question.lower())
                normalized_answer = self.bot._normalize_text_answer(question, answer, field_id)
                normalized_answer = self.bot.questions.humanize_free_text_answer(
                    question,
                    normalized_answer,
                    "textarea" if tag_name == "textarea" else "text",
                ).strip()
                if not normalized_answer:
                    normalized_answer = "N/A"

                is_typeahead = field.get_attribute("role") == "combobox" or field.get_attribute(
                    "aria-autocomplete"
                ) in ("list", "both")
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
            except Exception as exc:
                log.debug(f"Failed to recover empty field: {exc}")
                continue
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
                except Exception as exc:
                    log.debug(f"Failed to clear/fill error field '{input_id}': {exc}")
                    continue
        except Exception as exc:
            log.debug(f"Failed to process inline validation recovery: {exc}")
            return recovered
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
            log.debug(f"Failed to uncheck follow company check: {exc}")
