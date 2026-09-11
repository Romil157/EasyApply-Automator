"""Service for question parsing, normalization, answer coercion, and form filling."""

from __future__ import annotations

import re
import time

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from easy_apply_automator.config.timing import QUESTION_LOAD_PAUSE_SECONDS
from easy_apply_automator.observability.logger import log

from .base import ServiceBase


class QuestionService(ServiceBase):
    """Analyzes form labels/attributes and fills out text inputs, select dropdowns, and checkboxes."""

    def looks_numeric_question(self, question: str, input_id: str = "") -> bool:
        q = (question or "").lower()
        i = (input_id or "").lower()
        numeric_markers = (
            "how many years",
            "years of",
            "years experience",
            "year of experience",
            "experience do you have",
            "decimal number",
            "numeric",
            "number",
        )
        return any(marker in q for marker in numeric_markers) or "numeric" in i

    @staticmethod
    def clamp_to_field_limit(input_element, answer: str, question: str = "") -> str:
        if not answer or input_element is None:
            return answer

        # 1. HTML attribute maxlength
        try:
            max_len_attr = input_element.get_attribute("maxlength")
            if max_len_attr:
                try:
                    limit = int(max_len_attr)
                    if 0 < limit < 50000:
                        if len(answer) > limit:
                            log.info(f"Clamping answer from {len(answer)} to maxlength {limit}")
                            return answer[:limit].rstrip()
                except (ValueError, TypeError):
                    pass
        except Exception:
            pass

        # 2. Parent container character limit counter or hint
        try:
            parent = input_element.find_element(
                By.XPATH,
                "./ancestor::div[contains(@class, 'fb-dash-form-element') or contains(@class, 'jobs-easy-apply-form-element')][1]",
            )
            char_counters = parent.find_elements(
                By.CSS_SELECTOR,
                "span[class*='character-count'], span[class*='char-count'], span[aria-live], div[class*='character-count']",
            )
            for counter in char_counters:
                text = (counter.text or "").strip()
                match = re.search(r"/\s*(\d+)", text) or re.search(r"max(?:imum)?\s*(\d+)", text, re.I)
                if match:
                    limit = int(match.group(1))
                    if 0 < limit < 50000 and len(answer) > limit:
                        log.info(f"Clamping answer from {len(answer)} to counter limit {limit}")
                        return answer[:limit].rstrip()
        except Exception:
            pass

        # 3. Single-line headline fields on LinkedIn commonly have strict character limits (typically 100 or 120 chars)
        q_lower = (question or "").lower()
        tag = ""
        try:
            tag = (input_element.tag_name or "").lower()
        except Exception:
            pass
        if tag == "input" and "headline" in q_lower and len(answer) > 100:
            log.info(f"Headline single-line input detected with long text ({len(answer)} chars); trimming to 100 chars")
            truncated = answer[:100]
            last_space = truncated.rfind(" ")
            if last_space > 50:
                truncated = truncated[:last_space]
            return truncated.rstrip()

        return answer

    def coerce_numeric_answer(self, question: str, answer: str) -> str:
        q_lower = (question or "").lower()
        raw = re.sub(r"[,$€£]", "", (answer or "").strip())
        match = re.search(r"-?\d+(?:\.\d+)?", raw)
        val_float: float | None = None
        orig_val: str | None = None
        if match:
            orig_val = match.group(0)
            try:
                if float(orig_val) >= 0:
                    val_float = float(orig_val)
            except ValueError as exc:
                log.debug(f"Failed to convert value '{orig_val}' to float: {exc}")

        # Check if question requires a minimum or floor value e.g. "larger than 100"
        min_match = re.search(
            r"(?:larger than|greater than|more than|at least|minimum(?:\s+of)?)\s*(\d+(?:\.\d+)?)",
            q_lower,
        )
        if min_match:
            try:
                floor_val = float(min_match.group(1))
                if val_float is None or val_float <= floor_val:
                    if any(strict in q_lower for strict in ("larger than", "greater than", "more than")):
                        adjusted = floor_val + 1 if floor_val.is_integer() else floor_val + 0.1
                    else:
                        adjusted = floor_val
                    if "whole number" in q_lower or adjusted.is_integer():
                        return str(int(adjusted))
                    return str(adjusted)
            except Exception:
                pass

        if val_float is not None and orig_val is not None:
            return orig_val

        # Check if auto_answer has extracted years for this skill
        if hasattr(self.bot, "auto_answer") and self.bot.auto_answer is not None:
            extract_fn = getattr(self.bot.auto_answer, "_extract_skill_years", None)
            if callable(extract_fn):
                extracted = extract_fn(question)
                if isinstance(extracted, str):
                    return extracted

        if hasattr(self.bot, "auto_answer") and self.bot.auto_answer is not None:
            cfg = getattr(self.bot.auto_answer, "cfg", None)
            if isinstance(cfg, dict):
                return str(cfg.get("defaults", {}).get("unknown_years", "1"))

        return "1"

    def normalize_text_answer(self, question: str, answer: str, input_id: str = "") -> str:
        normalized = (answer or "").strip()
        if self.looks_numeric_question(question, input_id):
            return self.coerce_numeric_answer(question, normalized)
        if normalized.startswith("{") and normalized.endswith("}"):
            normalized = normalized[1:-1].strip()
        return normalized

    @staticmethod
    def clean_question_text(question: str) -> str:
        q = (question or "").strip()
        q = re.sub(r"(?i)\bplease enter a valid answer\b", "", q)
        q = re.sub(r"(.{10,})\s*\1+", r"\1", q)
        q = re.sub(r"\s+", " ", q).strip()
        return q

    @staticmethod
    def answer_aliases(answer: str) -> set[str]:
        a = (answer or "").strip().lower()
        aliases = {a}
        if a == "yes":
            aliases.update({"true", "y", "1"})
        elif a == "no":
            aliases.update({"false", "n", "0"})
        elif a in {"true", "1"}:
            aliases.update({"yes", "y"})
        elif a in {"false", "0"}:
            aliases.update({"no", "n"})
        return aliases

    def radio_matches_answer(self, field, radio, answer: str) -> bool:
        aliases = self.answer_aliases(answer)
        if not aliases:
            return False

        candidates: list[str] = []
        value = (radio.get_attribute("value") or "").strip().lower()
        aria = (radio.get_attribute("aria-label") or "").strip().lower()
        rid = (radio.get_attribute("id") or "").strip()
        if value:
            candidates.append(value)
        if aria:
            candidates.append(aria)
        if rid:
            try:
                label = field.find_element(By.CSS_SELECTOR, f"label[for='{rid}']")
                ltxt = (label.text or "").strip().lower()
                if ltxt:
                    candidates.append(ltxt)
            except NoSuchElementException as exc:
                log.debug(f"Label element for rid '{rid}' not found: {exc}")

        for c in candidates:
            c_norm = re.sub(r"\s+", " ", c)
            for a in aliases:
                if c_norm == a:
                    return True
                if re.search(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])", c_norm):
                    return True
        return False

    def compose_long_form_answer(self, question: str) -> str:
        q = (question or "").lower()
        templates = {}
        if hasattr(self.bot, "auto_answer") and self.bot.auto_answer is not None:
            cfg = getattr(self.bot.auto_answer, "cfg", None)
            if isinstance(cfg, dict):
                templates = cfg.get("long_form_templates", {})

        render_fn = None
        if hasattr(self.bot, "auto_answer") and self.bot.auto_answer is not None:
            render_fn = getattr(self.bot.auto_answer, "_render", None)

        def _format_tmpl(tmpl: str) -> str:
            if callable(render_fn):
                return render_fn(tmpl)
            return tmpl

        if "mission" in q or "what about" in q or ("why " in q and "role" not in q):
            if templates and "mission" in templates:
                return _format_tmpl(templates["mission"])
            return (
                "Your mission resonates with me because it focuses on building impactful, high-reliability software. "
                "With hands-on experience across modern software systems, data pipelines, "
                "and applied technologies, I am motivated by engineering teams that prioritize technical rigor, "
                "user experience, and continuous learning."
            )
        if "proud" in q or "project" in q or "tell us" in q:
            if templates and "project" in templates:
                return _format_tmpl(templates["project"])
            return (
                "A project I am most proud of is an end-to-end automation and analytics application that I built to "
                "streamline real-time data processing, integrate web services, and significantly improve workflow efficiency "
                "with robust error handling and observability."
            )
        if templates and "default" in templates:
            return _format_tmpl(templates["default"])
        return (
            "I am excited about this role because it aligns with my technical background and "
            "practical experience in software engineering, backend systems, and problem solving. "
            "I focus on writing clean, maintainable code, collaborating effectively in cross-functional teams, "
            "and delivering reliable solutions."
        )

    def is_long_form_prompt(self, question: str, input_type: str = "text") -> bool:
        q = (question or "").lower()
        if input_type == "textarea":
            return True
        markers = (
            "what about",
            "why ",
            "mission",
            "tell us",
            "describe",
            "project",
            "proud",
            "interests you",
            "motivate",
        )
        return any(m in q for m in markers)

    def humanize_free_text_answer(
        self, question: str, answer: str, input_type: str = "text"
    ) -> str:
        q = (question or "").strip()
        normalized = (answer or "").strip()
        low = normalized.lower()
        q_low = q.lower()

        placeholder_values = {
            "",
            "user provided",
            "n/a",
            "na",
            "none",
            "unknown",
            "not sure",
        }

        if any(
            marker in q_low
            for marker in (
                "if you do not require any adjustment",
                "adjustments to our recruitment process",
                "accommodation",
                "reasonable accommodation",
            )
        ):
            return normalized if low not in placeholder_values else "N/A"

        if self.is_long_form_prompt(q, input_type):
            if low in placeholder_values or len(normalized) < (
                60 if input_type == "textarea" else 40
            ):
                return self.compose_long_form_answer(q)
            if not normalized.endswith((".", "!", "?")):
                return normalized + "."
            return normalized

        if self.looks_numeric_question(q):
            return normalized
        if low in {self.bot.location_city.lower(), self.bot.location_country.lower()}:
            return normalized
        if low in {"yes", "no", "wish not to answer", "i do not wish to self-identify"}:
            return normalized

        skip_generic_markers = (
            "linkedin",
            "profile url",
            "github",
            "portfolio",
            "website",
            "salary",
            "compensation",
            "expected pay",
            "annual pay",
        )
        if any(m in q_low for m in skip_generic_markers) and low in placeholder_values:
            return ""

        if low in placeholder_values:
            return (
                "I enjoy solving practical engineering problems with clear user impact, and I value collaboration, "
                "ownership, and continuous improvement in how software is built and operated."
            )

        if input_type == "textarea" and len(normalized) < 40:
            return (
                normalized
                + " I focus on delivering reliable, maintainable solutions with measurable impact."
            ).strip()
        return normalized

    def derive_direct_answer(self, question: str, input_id: str = "") -> str | None:
        q = (question or "").lower()
        i = (input_id or "").lower()
        if (
            ("location" in q and "city" in q)
            or ("city" in q and "location" in q)
            or ("location-city" in i)
        ):
            return self.bot.location_city
        if (
            "phone country code" in q
            or ("country" in q and "city" not in q)
            or ("location-country" in i)
            or ("country" in i and "city" not in i)
        ):
            return self.bot.location_country
        return None

    def process_questions(self) -> None:
        time.sleep(QUESTION_LOAD_PAUSE_SECONDS)
        form = []
        seen_ids = set()
        selectors = [
            (By.CLASS_NAME, "jobs-easy-apply-form-section__grouping"),
            (By.CSS_SELECTOR, ".jobs-easy-apply-form-section__grouping"),
            (By.CSS_SELECTOR, "fieldset"),
            (By.CSS_SELECTOR, ".fb-form-element"),
            (By.CSS_SELECTOR, ".fb-dash-form-element"),
            (By.CSS_SELECTOR, ".jobs-easy-apply-form-element"),
            (By.CSS_SELECTOR, "div[data-test-form-element]"),
            (By.CSS_SELECTOR, ".artdeco-text-input"),
        ]
        for by, value in selectors:
            try:
                for field in self.bot.browser.find_elements(by, value):
                    fid = getattr(field, "id", None) or id(field)
                    if fid in seen_ids:
                        continue
                    seen_ids.add(fid)
                    form.append(field)
            except Exception as exc:
                log.debug(f"Failed to find elements by {by} with value {value}: {exc}")
                continue
        for field in form:
            question = self.clean_question_text(field.text)
            if not question:
                continue
            direct = self.derive_direct_answer(question)
            answer = direct if direct is not None else self.ans_question(question.lower())
            answered = False

            try:
                radios = field.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                if radios:
                    for radio in radios:
                        rid = radio.get_attribute("id") or ""
                        val = (radio.get_attribute("value") or "").strip().lower()
                        if self.radio_matches_answer(field, radio, answer) or (val and val == (answer or "").strip().lower()):
                            label_clicked = False
                            if rid:
                                try:
                                    label_el = field.find_element(By.CSS_SELECTOR, f"label[for='{rid}']")
                                    self.bot._safe_click(label_el)
                                    label_clicked = True
                                except Exception:
                                    pass
                            if not label_clicked:
                                self.bot._safe_click(radio)
                            self.bot.log_event("question_answered", kind="radio", question=question, answer=answer)
                            answered = True
                            break
                    if not answered:
                        for label in field.find_elements(By.TAG_NAME, "label"):
                            if (label.text or "").strip().lower() in self.answer_aliases(answer):
                                self.bot._safe_click(label)
                                self.bot.log_event("question_answered", kind="radio_label", question=question, answer=answer)
                                answered = True
                                break
                if answered:
                    continue
            except Exception as exc:
                log.debug(f"Failed to process radios for question '{question}': {exc}")

            try:
                selects = field.find_elements(By.TAG_NAME, "select")
                if selects:
                    if self.bot._select_option_by_answer(selects[0], answer):
                        self.bot.log_event("question_answered", kind="select", question=question, answer=answer)
                    elif self.bot._select_non_default_option(selects[0]):
                        self.bot.log_event("question_answered", kind="select_fallback", question=question, answer=answer)
                    continue
            except Exception as exc:
                log.debug(f"Failed to process selects for question '{question}': {exc}")

            try:
                multi = field.find_element(
                    By.XPATH, ".//*[contains(@id, 'text-entity-list-form-component')]"
                )
                multi.clear()
                multi.send_keys(answer)
                continue
            except Exception as exc:
                log.debug(
                    f"Failed to process multi text component for question '{question}': {exc}"
                )

            try:
                text_area = None
                try:
                    text_area = field.find_element(By.TAG_NAME, "textarea")
                except Exception as exc:
                    log.debug(f"TextArea element lookup failed in question '{question}': {exc}")
                    text_area = None

                if text_area is not None:
                    text_input_id = text_area.get_attribute("id") or ""
                    normalized_answer = self.normalize_text_answer(question, answer, text_input_id)
                    normalized_answer = self.humanize_free_text_answer(
                        question, normalized_answer, "textarea"
                    )
                    normalized_answer = self.clamp_to_field_limit(text_area, normalized_answer, question)
                    text_area.clear()
                    text_area.send_keys(normalized_answer)
                    self.bot.log_event(
                        "question_answered",
                        kind="textarea",
                        question=question,
                        answer=normalized_answer,
                    )
                    continue

                text_input = None
                for selector in [
                    ".artdeco-text-input--input",
                    "input[type='text']",
                    "input[type='number']",
                    "input:not([type='radio']):not([type='checkbox']):not([type='file']):not([type='submit'])",
                ]:
                    try:
                        candidate = field.find_element(By.CSS_SELECTOR, selector)
                        if candidate.is_displayed() and candidate.is_enabled():
                            text_input = candidate
                            break
                    except Exception:
                        continue

                if text_input is not None:
                    text_input_id = text_input.get_attribute("id") or ""
                    normalized_answer = self.normalize_text_answer(question, answer, text_input_id)
                    normalized_answer = self.humanize_free_text_answer(
                        question, normalized_answer, "text"
                    )
                    normalized_answer = self.clamp_to_field_limit(text_input, normalized_answer, question)
                    is_typeahead = text_input.get_attribute(
                        "role"
                    ) == "combobox" or text_input.get_attribute("aria-autocomplete") in ("list", "both")
                    if is_typeahead:
                        self.bot._fill_typeahead_input(text_input, normalized_answer)
                    else:
                        text_input.clear()
                        text_input.send_keys(normalized_answer)
                    self.bot.log_event(
                        "question_answered",
                        kind="typeahead" if is_typeahead else "text",
                        question=question,
                        answer=normalized_answer,
                    )
            except Exception as exc:
                log.debug(f"Unable to answer question '{question}': {exc}")

    def ans_question(self, question: str) -> str:
        return self.bot.auto_answer.ans_question(question)
