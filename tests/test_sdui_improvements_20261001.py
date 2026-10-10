"""Unit tests verifying fixes for SDUI progress detection, timeout prevention, and question handling."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from selenium.webdriver.common.by import By

from easy_apply_automator.qa.auto_answer import AutoAnswer
from easy_apply_automator.services.apply_flow_service import ApplyFlowService
from easy_apply_automator.services.question_service import QuestionService


class TestSDUIProgressDetection:
    def test_progressbar_svg_aria_valuenow(self):
        svc = ApplyFlowService.__new__(ApplyFlowService)
        bot = MagicMock()
        browser = MagicMock()

        # Artdeco progress element not found
        browser.find_element.side_effect = Exception("Not found")

        # Mock [role='progressbar'][aria-valuenow]
        pb = MagicMock()
        pb.get_attribute.side_effect = lambda attr: "60" if attr == "aria-valuenow" else None

        def find_elements(by, selector):
            if by == By.CSS_SELECTOR and "[role='progressbar']" in selector:
                return [pb]
            return []

        browser.find_elements.side_effect = find_elements
        bot.browser = browser
        svc.bot = bot
        svc.find_easy_apply_modal = MagicMock(return_value=None)

        progress = svc.get_easy_apply_progress()
        assert progress == 60

    def test_sdui_modal_percent_text(self):
        svc = ApplyFlowService.__new__(ApplyFlowService)
        bot = MagicMock()
        browser = MagicMock()

        browser.find_element.side_effect = Exception("Not found")
        browser.find_elements.return_value = []
        bot.browser = browser
        svc.bot = bot

        modal = MagicMock()
        modal.text = "75 percent complete\n3/4 pages\nAdditional Questions"
        svc.find_easy_apply_modal = MagicMock(return_value=modal)

        progress = svc.get_easy_apply_progress()
        assert progress == 75

    def test_sdui_modal_pages_fraction_text(self):
        svc = ApplyFlowService.__new__(ApplyFlowService)
        bot = MagicMock()
        browser = MagicMock()

        browser.find_element.side_effect = Exception("Not found")
        browser.find_elements.return_value = []
        bot.browser = browser
        svc.bot = bot

        modal = MagicMock()
        modal.text = "Step 3/5 pages\nQuestions"
        svc.find_easy_apply_modal = MagicMock(return_value=modal)

        progress = svc.get_easy_apply_progress()
        assert progress == 60


class TestResumeCardExclusion:
    def test_get_field_question_text_ignores_pdf_file_cards(self):
        svc = QuestionService.__new__(QuestionService)
        svc.clean_question_text = lambda x: (x or "").strip()

        field = MagicMock()
        field.get_attribute.return_value = ""
        field.text = "romil doshi resume (1).pdf\nUploaded on Sep 2026"

        assert svc.get_field_question_text(field) == ""

    def test_get_field_question_text_ignores_resume_card_component(self):
        svc = QuestionService.__new__(QuestionService)
        svc.clean_question_text = lambda x: (x or "").strip()

        field = MagicMock()
        field.get_attribute.side_effect = lambda attr: "jobs-document-upload-resume-card" if attr == "class" else ""
        field.text = "My Resume"

        assert svc.get_field_question_text(field) == ""


class TestQuestionAnsweringCoverage:
    @pytest.fixture
    def auto_answer(self):
        log = MagicMock()
        return AutoAnswer(
            qa_file=None,
            ans_yaml_path=Path("questions_answers.yaml"),
            salary="1000000",
            hourly_rate="500",
            answers={},
            log=log,
        )

    def test_have_completed_degree_answers_yes(self, auto_answer):
        q = "Have you completed the following level of education: Bachelor's Degree?*"
        ans = auto_answer.ans_question(q)
        assert ans.lower() == "yes"

    def test_english_proficiency_answers_professional(self, auto_answer):
        q = "What is your level of proficiency in English?*"
        ans = auto_answer.ans_question(q)
        assert ans.lower() in ("professional", "native or bilingual")

    def test_relocating_answers_yes(self, auto_answer):
        q = "Are you comfortable relocating to Bangalore for the role?  *"
        ans = auto_answer.ans_question(q)
        assert ans.lower() == "yes"

    def test_commuting_answers_yes(self, auto_answer):
        q = "Are you comfortable commuting to this job's location?*"
        ans = auto_answer.ans_question(q)
        assert ans.lower() == "yes"

    def test_onsite_setting_answers_yes(self, auto_answer):
        q = "Are you comfortable working in an onsite setting?*"
        ans = auto_answer.ans_question(q)
        assert ans.lower() == "yes"

    def test_us_shift_timings_answers_yes(self, auto_answer):
        q = "The work timings for this internship would be US shift (7 to 4 AM IST). Are you comfortable with that?*"
        ans = auto_answer.ans_question(q)
        assert ans.lower() == "yes"

    def test_laptop_availability_answers_yes(self, auto_answer):
        q = "Do you have a laptop, which you can use for the internship ?*"
        ans = auto_answer.ans_question(q)
        assert ans.lower() == "yes"

    def test_professional_experience_answers_one(self, auto_answer):
        for q in (
            "How many years of work experience do you currently have?*",
            "How many years of professional experience do you have?*",
            "Total years of experience",
            "How many years of total experience do you have?",
            "How many years of relevant experience do you have?",
            "Years of professional experience",
        ):
            ans = auto_answer.ans_question(q)
            assert ans == "1", f"Failed for '{q}', got '{ans}'"

    def test_it_services_experience_answers_one(self, auto_answer):
        q = "How many years of IT Services and IT Consulting experience do you currently have?*"
        ans = auto_answer.ans_question(q)
        assert ans == "1", f"Failed for '{q}', got '{ans}'"


class TestCircuitBreakerThreshold:
    def test_default_threshold_is_three(self):
        from easy_apply_automator.infra.human_simulation import AdaptiveCircuitBreaker
        cb = AdaptiveCircuitBreaker()
        assert cb.failure_threshold == 3

    def test_trips_after_three_consecutive_failures(self):
        from easy_apply_automator.infra.human_simulation import AdaptiveCircuitBreaker
        cb = AdaptiveCircuitBreaker()
        assert not cb.record_failure()
        assert not cb.record_failure()
        assert cb.record_failure()
        assert cb.total_cooldowns == 1
