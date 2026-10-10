# This is an internal module intended for mixin implementation only.
# Do not import it directly; use ApplyFlowService instead.
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from selenium.webdriver.common.by import By

from easy_apply_automator.observability.logger import log

if TYPE_CHECKING:
    from easy_apply_automator.app.orchestrator import LinkedInEasyApplyOrchestrator


@dataclass(slots=True)
class FollowCompanyStateResult:
    found: bool
    initial_state: bool | None
    final_state: bool | None
    changed: bool
    success: bool
    status: str
    error: str | None = None


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

    @staticmethod
    def _is_global_search_element(element) -> bool:
        """Returns True if the element belongs to LinkedIn's global navigation search."""
        try:
            el_class = (element.get_attribute("class") or "").lower()
            el_id = (element.get_attribute("id") or "").lower()
            placeholder = (element.get_attribute("placeholder") or "").lower()
            aria_label = (element.get_attribute("aria-label") or "").lower()
            name = (element.get_attribute("name") or "").lower()
            if (
                "search-global" in el_class
                or "global-nav-search" in el_id
                or "global-search" in el_id
                or "search-global-typeahead" in el_class
            ):
                return True
            if placeholder == "search" or aria_label == "search" or name == "search":
                return True
        except Exception:
            pass
        return False

    def _click_element_or_label(self, group, element, el_id: str) -> bool:
        """Helper to click label associated with an input or fallback to direct element click."""
        if el_id:
            try:
                label_el = group.find_element(By.CSS_SELECTOR, f"label[for='{el_id}']")
                if label_el.is_displayed() and self.bot._safe_click(label_el):
                    return True
            except Exception:
                pass
        try:
            container = element.find_element(By.XPATH, "./ancestor::*[@role='radio'][1]")
            if container.is_displayed() and self.bot._safe_click(container):
                return True
        except Exception:
            pass
        if self.bot._safe_click(element):
            return True
        try:
            self.bot.browser.execute_script("arguments[0].click();", element)
            return True
        except Exception:
            pass
        return False

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
                    digits = re.sub(r"[^\d]", "", self.bot.phone_number)
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
                if self._is_global_search_element(input_el):
                    continue
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
            radios = group.find_elements(By.CSS_SELECTOR, "input[type='radio'], div[role='radio']")
            if not radios:
                return False

            has_checked = any(
                r.is_selected() or (r.get_attribute("aria-checked") == "true")
                for r in radios
            )
            if has_checked:
                return False

            question = ""
            if hasattr(self.bot, "questions") and hasattr(self.bot.questions, "get_field_question_text"):
                question = self.bot.questions.get_field_question_text(group)
            if not question:
                raw_question = group.text or ""
                question = self.bot._clean_question_text(raw_question)
            if not question or question.lower() in ("yes no", "yes", "no"):
                return False
            if re.search(r"\.(pdf|docx?|txt|rtf)\b", question, re.IGNORECASE):
                return False

            direct = self.bot._derive_direct_answer(question)
            answer = direct if direct is not None else self.bot.ans_question(question.lower())
            answer_aliases = self.bot._answer_aliases(answer)

            # Strategies: match by answer aliases, then yes/true, then no/false
            for radio in radios:
                rid = radio.get_attribute("id") or ""
                val = (radio.get_attribute("value") or "").strip().lower()
                matched = self.bot._radio_matches_answer(group, radio, answer) or (val and val in answer_aliases)
                kind = "required_radio_recovery"
                if not matched and ({"yes", "true", "1", "y"} & answer_aliases) and val in {"true", "yes", "1"}:
                    matched = True
                    kind = "required_radio_yes_fallback"
                elif not matched and ({"no", "false", "0", "n"} & answer_aliases) and val in {"false", "no", "0"}:
                    matched = True
                    kind = "required_radio_no_fallback"

                if matched and self._click_element_or_label(group, radio, rid):
                    self.bot.log_event("question_answered", kind=kind, question=question, answer=answer)
                    return True

            # Binary Yes/No fallback if answer is affirmative or question is binary
            all_vals = set()
            for r in radios:
                v = (r.get_attribute("value") or "").strip().lower()
                if v:
                    all_vals.add(v)
                rid = r.get_attribute("id") or ""
                if rid:
                    try:
                        lbl = group.find_element(By.CSS_SELECTOR, f"label[for='{rid}']")
                        ltxt = (lbl.text or "").strip().lower()
                        if ltxt:
                            all_vals.add(ltxt)
                    except Exception:
                        pass
            if all_vals and all_vals.issubset({"yes", "no", "true", "false", "1", "0"}):
                target = "no" if (answer or "").strip().lower() in ("no", "false", "0") else "yes"
                target_aliases = {"yes", "true", "1", "y"} if target == "yes" else {"no", "false", "0", "n"}
                for r in radios:
                    rid = r.get_attribute("id") or ""
                    val = (r.get_attribute("value") or "").strip().lower()
                    lbl_txt = ""
                    if rid:
                        try:
                            lbl = group.find_element(By.CSS_SELECTOR, f"label[for='{rid}']")
                            lbl_txt = (lbl.text or "").strip().lower()
                        except Exception:
                            pass
                    if (val in target_aliases) or (lbl_txt in target_aliases):
                        if self._click_element_or_label(group, r, rid):
                            self.bot.log_event("question_answered", kind="required_radio_binary_fallback", question=question, answer=target)
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
                ".jobs-easy-apply-form-section__grouping, fieldset, div[role='radiogroup'], "
                "div[componentkey*='easyApply'], .fb-form-element, .fb-dash-form-element, "
                ".jobs-easy-apply-form-element, div[data-test-form-element]",
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
                ".jobs-easy-apply-form-section__grouping, fieldset, div[role='radiogroup'], "
                "div[componentkey*='easyApply'], .fb-form-element, .fb-dash-form-element, "
                ".jobs-easy-apply-form-element, div[data-test-form-element]",
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
                    if self._is_global_search_element(input_el):
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
                    if hasattr(self.bot, "questions") and hasattr(self.bot.questions, "clamp_to_field_limit"):
                        final_val = self.bot.questions.clamp_to_field_limit(input_el, coerced, question)
                    else:
                        final_val = coerced
                    input_el.clear()
                    input_el.send_keys(final_val or "0")
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
                    cb_aria = (cb.get_attribute("aria-label") or "").lower()
                    if "follow-company" in cb_id or ("follow" in cb_aria and "stay up to date" in cb_aria):
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
                    if self._is_global_search_element(box):
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

    def find_follow_company_controls(self, container: Any = None) -> tuple[Any, Any] | None:
        """Locates the follow company control in the active modal or container.

        Returns a tuple of (primary_control, alternate_control) or None if not found.
        Unrelated checkboxes (terms, job alerts, switches) are strictly ignored.
        """
        root = container if container is not None else self.bot.browser
        follow_pattern = re.compile(r"follow\s+.+?\s+to\s+stay\s+up\s+to\s+date", re.IGNORECASE)

        # Strategy 1: Look for custom role='checkbox' with follow text in aria-label
        try:
            custom_cbs = root.find_elements(By.CSS_SELECTOR, "div[role='checkbox'], span[role='checkbox']")
            for cb in custom_cbs:
                try:
                    aria_label = (cb.get_attribute("aria-label") or "").strip()
                    if follow_pattern.search(aria_label) or ("follow" in aria_label.lower() and "stay up to date" in aria_label.lower()):
                        sub_labels = cb.find_elements(By.TAG_NAME, "label")
                        sub_inputs = cb.find_elements(By.TAG_NAME, "input")
                        alt = sub_labels[0] if sub_labels else (sub_inputs[0] if sub_inputs else None)
                        return (cb, alt)
                except Exception:
                    continue
        except Exception as exc:
            log.debug(f"Custom checkbox search failed: {exc}")

        # Strategy 2: Look for elements with follow text, then traverse to checkbox container or label
        try:
            text_candidates = root.find_elements(
                By.XPATH,
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'follow') "
                "and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'stay up to date')]"
            )
            for cand in text_candidates:
                try:
                    enclosing = cand.find_elements(By.XPATH, "./ancestor::*[@role='checkbox'][1]")
                    if enclosing:
                        sub_labels = enclosing[0].find_elements(By.TAG_NAME, "label")
                        alt = sub_labels[0] if sub_labels else cand
                        return (enclosing[0], alt)
                    ancestor_label = cand.find_elements(By.XPATH, "./ancestor::label[1]")
                    if ancestor_label:
                        for_id = ancestor_label[0].get_attribute("for")
                        inp = root.find_element(By.ID, for_id) if for_id else None
                        return (ancestor_label[0], inp)
                    ancestor_div = cand.find_elements(By.XPATH, "./ancestor::div[1]")
                    if ancestor_div:
                        inputs = ancestor_div[0].find_elements(By.TAG_NAME, "input")
                        if inputs:
                            return (inputs[0], cand)
                except Exception:
                    continue
        except Exception as exc:
            log.debug(f"Text-anchored follow search failed: {exc}")

        # Strategy 3: Legacy follow-company checkbox ID or name
        try:
            legacy_inputs = root.find_elements(
                By.CSS_SELECTOR,
                "input#follow-company-checkbox, input[id*='follow-company'], input[name*='followCompany']"
            )
            for inp in legacy_inputs:
                try:
                    inp_id = inp.get_attribute("id") or ""
                    labels = root.find_elements(By.CSS_SELECTOR, f"label[for='{inp_id}']") if inp_id else []
                    label = labels[0] if labels else None
                    return (label or inp, inp if label else None)
                except Exception:
                    continue
        except Exception as exc:
            log.debug(f"Legacy follow checkbox search failed: {exc}")

        # Strategy 4: Fallback to locators.yaml definitions
        loc_follow = getattr(self.bot, "locator", {}).get("follow")
        if loc_follow:
            try:
                elems = root.find_elements(loc_follow[0], loc_follow[1])
                for el in elems:
                    try:
                        txt = (el.text or "") + " " + (el.get_attribute("aria-label") or "")
                        if "follow" in txt.lower():
                            return (el, None)
                    except Exception:
                        continue
            except Exception as exc:
                log.debug(f"Locators follow lookup failed: {exc}")

        return None

    def inspect_follow_company_state(self, primary: Any, alternate: Any = None) -> bool | None:
        """Inspects whether the follow company control is checked (True), unchecked (False), or unknown (None)."""
        elements = [el for el in (primary, alternate) if el is not None]
        for el in elements:
            try:
                # 1. role='checkbox' aria-checked attribute
                aria_checked = el.get_attribute("aria-checked")
                if aria_checked is not None:
                    aria_checked_str = str(aria_checked).strip().lower()
                    if aria_checked_str == "true":
                        return True
                    if aria_checked_str == "false":
                        return False

                # 2. native checkbox input
                tag = (el.tag_name or "").lower()
                if tag == "input":
                    if el.is_selected():
                        return True
                    checked_attr = el.get_attribute("checked")
                    if checked_attr is not None and str(checked_attr).lower() in ("true", "checked", ""):
                        return el.is_selected()
                    return False

                # 3. Check child input inside container
                child_inputs = el.find_elements(By.TAG_NAME, "input")
                for c_inp in child_inputs:
                    try:
                        if (c_inp.get_attribute("type") or "").lower() == "checkbox":
                            if c_inp.is_selected():
                                return True
                            c_aria = c_inp.get_attribute("aria-checked")
                            if c_aria is not None:
                                return str(c_aria).strip().lower() == "true"
                    except Exception:
                        pass
            except Exception as exc:
                log.debug(f"Error inspecting follow checkbox state on {el}: {exc}")
                continue

        # If child inputs exist on primary and none returned True, check if is_selected is False
        for el in elements:
            try:
                child_inputs = el.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
                if child_inputs:
                    return child_inputs[0].is_selected()
            except Exception:
                pass

        return None

    def set_follow_company_state(
        self, desired_state: bool = False, require_present: bool = True
    ) -> FollowCompanyStateResult:
        """Idempotent state-setting controller for the follow company checkbox.

        Workflow:
        1. Inspect current state.
        2. If already in desired state, do nothing (idempotent).
        3. If not in desired state, click primary accessible control.
        4. If state still unchanged, retry once using alternate associated control.
        5. Verify final state and return structured result.
        """
        modal = getattr(self, "find_easy_apply_modal", lambda: None)()
        controls = self.find_follow_company_controls(container=modal)

        if controls is None:
            if require_present:
                err_msg = "Follow company checkbox control could not be found on the page."
                log.warning(err_msg)
                return FollowCompanyStateResult(
                    found=False,
                    initial_state=None,
                    final_state=None,
                    changed=False,
                    success=False,
                    status="element_not_found",
                    error=err_msg,
                )
            return FollowCompanyStateResult(
                found=False,
                initial_state=None,
                final_state=None,
                changed=False,
                success=True,
                status="not_present_not_required",
            )

        primary, alternate = controls
        initial_state = self.inspect_follow_company_state(primary, alternate)

        if initial_state is None:
            err_msg = "Follow company checkbox initial state could not be determined."
            log.warning(err_msg)
            return FollowCompanyStateResult(
                found=True,
                initial_state=None,
                final_state=None,
                changed=False,
                success=False,
                status="initial_state_unknown",
                error=err_msg,
            )

        # Idempotence: if already in desired state, do not click
        if initial_state == desired_state:
            log.info(f"Follow company checkbox is already in desired state ({desired_state}). No action taken.")
            return FollowCompanyStateResult(
                found=True,
                initial_state=initial_state,
                final_state=initial_state,
                changed=False,
                success=True,
                status="already_in_desired_state",
            )

        # Primary action attempt
        target = alternate if alternate is not None and (getattr(alternate, "tag_name", "") or "").lower() == "label" else primary
        log.info(f"Setting follow company checkbox from {initial_state} to {desired_state} via {getattr(target, 'tag_name', 'control')}...")

        self.bot._safe_click(target)
        time.sleep(0.25)

        mid_state = self.inspect_follow_company_state(primary, alternate)
        if mid_state == desired_state:
            log.info(f"Follow company checkbox successfully set to {desired_state}.")
            return FollowCompanyStateResult(
                found=True,
                initial_state=initial_state,
                final_state=mid_state,
                changed=True,
                success=True,
                status="transitioned_to_desired_state",
            )

        # Retry once using alternate control if state still not in desired state
        alt_target = primary if target is alternate else alternate
        if alt_target is not None:
            log.info(f"Follow company checkbox state remains {mid_state}. Retrying via alternate control...")
            self.bot._safe_click(alt_target)
            time.sleep(0.25)
        else:
            try:
                self.bot.browser.execute_script("arguments[0].click();", target)
                time.sleep(0.25)
            except Exception:
                pass

        final_state = self.inspect_follow_company_state(primary, alternate)
        if final_state == desired_state:
            log.info(f"Follow company checkbox successfully set to {desired_state} after retry.")
            return FollowCompanyStateResult(
                found=True,
                initial_state=initial_state,
                final_state=final_state,
                changed=True,
                success=True,
                status="transitioned_to_desired_state_after_retry",
            )

        err_msg = f"Follow company checkbox state remains {final_state} (expected {desired_state}) after retry."
        log.error(err_msg)
        return FollowCompanyStateResult(
            found=True,
            initial_state=initial_state,
            final_state=final_state,
            changed=False,
            success=False,
            status="state_verification_failed",
            error=err_msg,
        )

    def uncheck_follow_company(self) -> None:
        """Backward-compatible helper to uncheck follow company checkbox."""
        res = self.set_follow_company_state(desired_state=False, require_present=False)
        if not res.success and res.error:
            log.debug(f"uncheck_follow_company: {res.error}")
