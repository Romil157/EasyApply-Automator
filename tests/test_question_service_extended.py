"""Extended tests for QuestionService logic."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from easy_apply_automator.services.question_service import QuestionService


@pytest.fixture
def service():
    mock_bot = MagicMock()
    mock_bot.location_city = "Mumbai"
    mock_bot.location_country = "India"
    return QuestionService(mock_bot)


class TestQuestionServiceLogic:
    def test_looks_numeric_question(self, service):
        assert service.looks_numeric_question("How many years of experience?") is True
        assert (
            service.looks_numeric_question("Years of python experience", "input_numeric_123")
            is True
        )
        assert service.looks_numeric_question("What is your name?") is False
        assert service.looks_numeric_question("", "") is False

    def test_coerce_numeric_answer(self, service):
        # Extract number
        assert service.coerce_numeric_answer("Years?", "5 years") == "5"
        assert service.coerce_numeric_answer("Years?", "$100,000") == "100000"

        # Zero is preserved, negative returns fallback
        assert service.coerce_numeric_answer("Years?", "0") == "0"
        assert service.coerce_numeric_answer("Years?", "-5") == "1"

        # Fallback values for unknown skills
        assert service.coerce_numeric_answer("How many years of Solidity?", "none") == "1"
        assert service.coerce_numeric_answer("Web3 experience?", "0") == "0"
        assert service.coerce_numeric_answer("How many years of UnknownTool?", "none") == "1"
        assert service.coerce_numeric_answer("Something else?", "none") == "1"

    def test_normalize_text_answer(self, service):
        # Numeric normalization
        assert service.normalize_text_answer("How many years?", "5 years") == "5"
        # Template removal
        assert service.normalize_text_answer("Question", "{my_answer}") == "my_answer"
        # Regular text
        assert service.normalize_text_answer("Question", "  Hello  ") == "Hello"

    def test_clean_question_text(self, service):
        assert service.clean_question_text("  Please enter a valid answer  ") == ""
        # The regex r"(.{12,}?)\1+" removes repetitions of 12+ characters.
        # "test test test test" is 4 * 5 chars, but it's not a single sequence of 12+ chars repeated.
        # Let's test a real repetition.
        assert (
            service.clean_question_text(
                "This is a long sentence that repeats. This is a long sentence that repeats."
            )
            == "This is a long sentence that repeats."
        )
        assert service.clean_question_text("Too    many    spaces") == "Too many spaces"

    def test_answer_aliases(self, service):
        assert service.answer_aliases("yes") == {"yes", "true", "y", "1"}
        assert service.answer_aliases("no") == {"no", "false", "n", "0"}
        assert service.answer_aliases("true") == {"true", "yes", "y"}
        assert service.answer_aliases("something") == {"something"}

    def test_is_long_form_prompt(self, service):
        assert service.is_long_form_prompt("Why do you want this role?") is True
        assert service.is_long_form_prompt("Describe your project", "text") is True
        assert service.is_long_form_prompt("What is your name?") is False
        assert service.is_long_form_prompt("Your name?", "textarea") is True

    def test_compose_long_form_answer(self, service):
        # Mission
        assert "mission resonates" in service.compose_long_form_answer("What is our mission?")
        # Project
        assert "project I am most proud of" in service.compose_long_form_answer("Tell us about a project")
        # Default
        assert "excited about this role" in service.compose_long_form_answer("Random question")

    def test_compose_long_form_answer_with_templates(self, service):
        service.bot.auto_answer = MagicMock()
        service.bot.auto_answer.cfg = {
            "long_form_templates": {
                "mission": "Custom mission text",
                "project": "Custom project text",
                "default": "Custom default text",
            }
        }
        service.bot.auto_answer._render = lambda t: t
        assert service.compose_long_form_answer("What is our mission?") == "Custom mission text"
        assert service.compose_long_form_answer("Tell us about a project") == "Custom project text"
        assert service.compose_long_form_answer("Random question") == "Custom default text"

    def test_humanize_free_text_answer(self, service):
        # Placeholder handling
        assert (
            service.humanize_free_text_answer("Question", "n/a", "text")
            == "I enjoy solving practical engineering problems with clear user impact, and I value collaboration, ownership, and continuous improvement in how software is built and operated."
        )

        # Long form prompt triggering
        assert "mission resonates" in service.humanize_free_text_answer(
            "Why us?", "too short", "text"
        )

        # Adjustment request
        assert (
            service.humanize_free_text_answer("Do you require accommodation?", "none", "text")
            == "N/A"
        )

        # Numeric questions should not be humanized
        assert service.humanize_free_text_answer("How many years?", "5", "text") == "5"

        # Location checks
        assert service.humanize_free_text_answer("City?", "Mumbai", "text") == "Mumbai"

        # TextArea minimum length - avoid "tell us" to not trigger project answer
        ans = service.humanize_free_text_answer("Random Question", "Hello", "textarea")
        assert "excited about this role" in ans

    def test_derive_direct_answer(self, service):
        assert service.derive_direct_answer("What is your location city?") == "Mumbai"
        assert service.derive_direct_answer("Country?", "location-country") == "India"
        assert service.derive_direct_answer("Random question") is None
